import sys
import os

sys.path.append(os.path.join('api', 'src', 'scripts'))
import datetime
import yaml
import api.src.common.initial_environment_config

from sklearn.preprocessing import LabelEncoder
from sklearn.base import BaseEstimator, TransformerMixin
from api.src.models.wide_resnet import create_wide_residual_network
from api.src.data_processing.data_generator import DataGenerator
from api.src.common.config import TrainingConfig, DataConfig, Config
from api.src.common.utils import print_info, ensure_dir
from api.src.scripts.plot_trainings import get_description_string
from api.src.common import config
from keras.optimizers import SGD, Adam

from hyperas import optim
from hyperas.distributions import choice, uniform, conditional
from hyperas.utils import eval_hyperopt_space
from hyperopt import Trials, STATUS_OK, tpe, rand
from keras.callbacks import ModelCheckpoint, CSVLogger, EarlyStopping
from api.src.keras_extensions.metrics import f1

import keras.backend as K


def get_running_time():
    return datetime.datetime.now().strftime("%H_%M_%d_%m_%y")


def data():
    data_generator_train = DataGenerator(DataConfig.PATHS['TRAINING_PROCESSED_DATA'], TrainingConfig.BATCH_SIZE,
                                         Config.IMAGE_SIZE, False)
    data_generator_valid = DataGenerator(DataConfig.PATHS['VALID_PROCESSED_DATA'], TrainingConfig.BATCH_SIZE,
                                         Config.IMAGE_SIZE, True)
    return data_generator_train, data_generator_valid


def train(data_generator_train, data_generator_valid):
    running_time = get_running_time()
    if not Config.NO_SAVE:
        ensure_dir(os.path.join(TrainingConfig.PATHS['MODELS'], running_time))

    if conditional({{choice(['scratch', 'pretrained'])}}) == 'pretrained':  # using pretrained weights
        model = create_wide_residual_network(Config.INPUT_SHAPE, N=2, k=8, dropout={{uniform(0.0, 0.9)}},
                                             path_weights=os.path.join(DataConfig.PATHS['PRETRAINED_MODEL_FOLDER'],
                                                                       'WRN-16-8 Weights.h5'),
                                             layer_to_stop_freezing={{choice([
                                                 'convolution2d_1', 'merge_2', 'convolution2d_3', 'merge_1'
                                             ])}})
    else:
        model = create_wide_residual_network(Config.INPUT_SHAPE, N={{choice([1, 2, 3, 4])}},
                                             k={{choice([1, 2, 4, 8, 10])}},
                                             dropout={{uniform(0.0, 0.9)}})

    callbacks = [
        ModelCheckpoint(os.path.join(TrainingConfig.PATHS['MODELS'], running_time, 'weights.h5'), save_best_only=True,
                        monitor=TrainingConfig.callbacks_monitor),
        CSVLogger(os.path.join(TrainingConfig.PATHS['MODELS'], running_time, 'history.csv')),
        EarlyStopping(patience=12)
    ] if not Config.NO_SAVE else []

    if not Config.NO_SAVE:
        with open(os.path.join(TrainingConfig.PATHS['MODELS'], running_time, 'config.yml'), 'w') as f:
            yaml.dump(list([TrainingConfig.get_config(), Config.get_config(), DataConfig.get_config()]), f,
                      default_flow_style=False)

        with open(os.path.join(TrainingConfig.PATHS['MODELS'], running_time, 'model.txt'), 'w') as f:
            f.write(get_description_string(model))

    model.compile({{choice([Adam(), Adam(0.02), SGD(0.02, momentum=0.9, nesterov=True)])}}, TrainingConfig.loss, metrics=TrainingConfig.metrics)

    model.fit_generator(data_generator_train, samples_per_epoch=data_generator_train.samples_per_epoch,
                        nb_epoch=TrainingConfig.NB_EPOCHS,
                        validation_data=data_generator_valid, nb_val_samples=data_generator_valid.samples_per_epoch,
                        callbacks=callbacks, class_weight=data_generator_train.get_class_weights)
    metrics = model.evaluate_generator(data_generator_valid, data_generator_valid.samples_per_epoch)
    print('Test accuracy: ', metrics[1])
    return {'loss': -metrics[1], 'status': STATUS_OK, 'model': model}


def main():
    running_time = get_running_time()
    trials = Trials()
    best_run, best_model, space = optim.minimize(model=train,
                                                 data=data,
                                                 algo=tpe.suggest,
                                                 functions=[
                                                     get_running_time,
                                                 ],
                                                 max_evals=3,
                                                 trials=trials,
                                                 eval_space=True,
                                                 # <-- this is the line that puts real values into 'best_run'
                                                 return_space=True
                                                 # <-- this allows you to save the space for later evaluations
                                                 )
    print_info("Training")
    print(best_run)
    best_model.save_weights(os.path.join(TrainingConfig.PATHS['MODELS'], running_time, 'best_of_all.h5'))
    print_info("Finished")
    for t, trial in enumerate(trials):
        vals = trial.get('misc').get('vals')
        print("Trial %s vals: %s" % (t, vals))
        print(eval_hyperopt_space(space, vals))


if __name__ == '__main__':
    main()
