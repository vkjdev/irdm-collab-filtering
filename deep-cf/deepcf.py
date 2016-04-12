from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf
import lastfm_reader as data_reader
from musicmodel import MusicModel
from modeltrainer import Trainer
from hooks import *


flags = tf.flags
logging = tf.logging

# Flags allows for processing of command-line arguments
flags.DEFINE_string("data_path", None, "data_path")
flags.DEFINE_string("mode", "train", "mode")
flags.DEFINE_string("model_path", None, "model_path")
FLAGS = flags.FLAGS


class ModelConfig(object):
    init_scale = 0.1
    max_grad_norm = 5
    num_layers = 2
    num_steps = 20
    hidden_size = 200
    embedding_size = 200
    num_epochs = 5
    batch_size = 1


def train(data_path, save_path):
    train_data, valid_data, test_data, songs = data_reader.get_data(data_path)
    song_to_id = data_reader.get_song_to_id_map(songs)

    train_config = ModelConfig()
    train_config.num_songs = len(songs)

    eval_config = ModelConfig()
    eval_config.batch_size = 1
    eval_config.num_steps = 1
    eval_config.num_songs = len(songs)

    with tf.Graph().as_default(), tf.Session() as session:
        initializer = tf.random_uniform_initializer(-train_config.init_scale,
                                                    train_config.init_scale)

        with tf.variable_scope("model", reuse=None, initializer=initializer):
            m = MusicModel(train_config)

        summary_writer = tf.train.SummaryWriter("./out/save", graph_def=session.graph_def)

        hooks = [
            TrainLossHook(summary_writer, "Training Loss"),
            GenericLossHook(valid_data, 'Validation', data_reader.session_iterator, data_reader.seq_iterator,
                            song_to_id, summary_writer, "Validation Loss")
        ]

        trainer = Trainer(m, train_data, song_to_id, data_reader.session_iterator, data_reader.seq_iterator, save_path)
        trainer.train(session, train_config.num_epochs, hooks)


def evaluate(data_path, model_path):
    # CALL THE RELEVANT EVALUATION CODE
    _, valid_data, test_data, songs = data_reader.get_data(data_path)
    song_to_id = data_reader.get_song_to_id_map(songs)

    eval_config = ModelConfig()
    eval_config.num_songs = len(songs)

    validation_hook = GenericLossHook(valid_data, 'Validation', data_reader.session_iterator, data_reader.seq_iterator,
                                      song_to_id, None, "Validation Loss")
    test_hook = GenericLossHook(test_data, 'Test', data_reader.session_iterator, data_reader.seq_iterator,
                                song_to_id, None, "Test Loss")

    with tf.Graph().as_default(), tf.Session() as session:

        with tf.variable_scope("model"):
            m = MusicModel(eval_config)

        saver = tf.train.Saver(tf.trainable_variables())
        saver.restore(session, model_path)

        validation_hook(session, m, 0, 0)
        test_hook(session, m, 0, 0)


def print_usage():
    print('For training: deepcf.py --mode training --data_path="[PATH-TO-DATA]" --model_path=[PATH-TO-SAVE-MODEL]')
    print('For evaluation: deepcf.py --mode evaluation --data_path="[PATH-TO-DATA]" --model_path=[PATH-TO-SAVED-MODEL]')


def main(_):
    if not FLAGS.mode or not FLAGS.data_path or not FLAGS.model_path:
        print_usage()
        raise ValueError("Missing parameter(s)")

    if FLAGS.mode == "training":
        train(FLAGS.data_path, FLAGS.model_path)
    elif FLAGS.mode == "evaluation":
        evaluate(FLAGS.data_path, FLAGS.model_path)
    else:
        print("Unrecognised mode: " + FLAGS.mode + " Please choose either 'training' or 'evaluation'")


if __name__ == "__main__":
    tf.app.run()