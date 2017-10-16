from keras.models import Model
from keras.layers import Convolution2D, BatchNormalization, MaxPooling2D, GlobalAveragePooling2D, Activation, Input, Dropout, Flatten
from api.src.common.config import Config, DataConfig


def bn_convo(x, filters, kernel_size, use_dropout=False):
    x = BatchNormalization(Config.CHANNEL_AXIS)(x)
    x = Activation(Config.ACTIVATION)(x)
    x = Convolution2D(filters, kernel_size, kernel_size,
                      border_mode='same', init=Config.WEIGHT_INIT)(x)
    if use_dropout:
        x = Dropout(0.5)(x)
    return x


def create_model():
    inputs = Input(Config.INPUT_SHAPE)

    filters = [32, 64, 128, DataConfig.get_number_of_classes()]
    repetitions = [2, 2, 3, 3]

    x = Convolution2D(16, 5, 5, init=Config.WEIGHT_INIT,
                      border_mode='same', subsample=(2, 2))(inputs)

    for index, (f, r) in enumerate(zip(filters, repetitions)):
        for _ in range(r):
            x = bn_convo(x, f, 3, use_dropout=True)
        if index - 1 < len(filters):
            x = MaxPooling2D((2, 2))(x)
    x = GlobalAveragePooling2D()(x)
    x = Activation('softmax')(x)
    model = Model(inputs, x, '3_convo')
    return model


if __name__ == '__main__':
    create_model().summary()
