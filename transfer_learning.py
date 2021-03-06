import logging
import os

import click
import keras
import matplotlib
import numpy as np
matplotlib.use("TKAgg",warn=False, force=True)

import matplotlib.pyplot as plt
from keras import Model
from keras.callbacks import TensorBoard, EarlyStopping, ModelCheckpoint
from keras.layers import Dense
from deepyeast.models import DeepYeast
from sklearn import model_selection
from sklearn.preprocessing import normalize
from sklearn.metrics import confusion_matrix


from load_dataset import load_dataset_rg

CHECKPOINT_PATH="weights-{epoch:02d}-{loss:.4f}.hdf5"

logging.getLogger().setLevel(logging.INFO)


@click.command(help="Fine tune the DeepYeast model.")
@click.option("-w", "--weights-path", prompt=True, type=str)
@click.option("-i", "--dataset-path", prompt=True, type=str)
@click.option("-l", "--labels-path", prompt=True, type=str)
def main(
    weights_path: str,
    dataset_path: str,
    labels_path: str,
) -> None:
    logging.info("Loading base model")
    base_model = DeepYeast()
    base_model.load_weights(weights_path)

    # add a new classification head
    relu5_features = base_model.get_layer("relu5").output
    scores = Dense(28, activation="sigmoid")(relu5_features)
    model = Model(inputs=base_model.input, outputs=scores)

    # fine-tune only fully-connected layers, freeze others
    # 23
    for layer in model.layers[:23]:
        layer.trainable = False

    if dataset_path.endswith(".dat") and labels_path.endswith(".dat"):
        X = np.memmap(dataset_path, dtype='float32', mode='r', shape=(638716, 64, 64, 2))
        y = np.memmap(labels_path, dtype='float32', mode='r', shape=(638716, 28))
    else:
        imgs_paths = [os.path.join(dataset_path, f) for f in os.listdir(dataset_path) if f.endswith(".png")]
        X, y = load_dataset_rg(imgs_paths, labels_path, 64, 64)

    X_train, X_val_test, y_train, y_val_test = model_selection.train_test_split(X, y, test_size=0.2, shuffle=True, random_state=42)
    X_val, X_test, y_val, y_test = model_selection.train_test_split(X_val_test, y_val_test, test_size=0.5, shuffle=True, random_state=42)
    
    X_train /= 255.
    X_train -= 0.5
    X_train *= 2.

    X_val /= 255.
    X_val -= 0.5
    X_val *= 2. 

    model.compile(
        loss=keras.losses.categorical_crossentropy,
        optimizer=keras.optimizers.SGD(lr=0.0001, momentum=0.9, nesterov=True),
        metrics=["accuracy"],
    )

    history = model.fit(
        X_train, y_train,
        batch_size=1024,
        epochs=100,
        validation_data=(X_val, y_val),
        callbacks=[
            # TensorBoard(log_dir=log_path, write_graph=True),
            EarlyStopping(monitor="val_loss", min_delta=0, patience=10, verbose=0, mode="auto"),
            ModelCheckpoint(CHECKPOINT_PATH, monitor="val_loss", verbose=1, save_best_only=True, mode="auto"),
        ]
    )

    plot_history(history)



def plot_history(history):
    plt.plot(history.history["acc"])
    plt.plot(history.history["val_acc"])
    plt.title("model accuracy")
    plt.ylabel("accuracy")
    plt.xlabel("epoch")
    plt.legend(["train", "val"], loc="upper left")
    plt.savefig("accuracy.png")

    # summarize history for loss
    plt.figure()
    plt.plot(history.history["loss"])
    plt.plot(history.history["val_loss"])
    plt.title("model loss")
    plt.ylabel("loss")
    plt.xlabel("epoch")
    plt.legend(["train", "val"], loc="upper left")
    plt.savefig("loss.png")


if __name__ == "__main__":
    main()
