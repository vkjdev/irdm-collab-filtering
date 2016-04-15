import tensorflow as tf


class Hook:
    def __init__(self, summary_writer, tag):
        self.summary_writer = summary_writer
        self.tag = tag

    def __call__(self, session, model, train_loss, epoch):
        raise NotImplementedError

    def update_summary(self, session, step, value):
        if self.summary_writer is not None:
            current_summary = tf.scalar_summary(self.tag, value)
            merged = tf.merge_summary([current_summary])
            summary_string = session.run(merged)
            self.summary_writer.add_summary(summary_string, step)


class TrainLossHook(Hook):
    def __init__(self, summary_writer, tag):
        Hook.__init__(self, summary_writer, tag)

    def __call__(self, session, model, train_loss, epoch):
        print("Epoch: %d Train Loss: %.3f" % (epoch, train_loss))
        self.update_summary(session, epoch, train_loss)


class GenericLossHook(Hook):
    def __init__(self, data, name, session_iterator, sequence_iterator, song_to_id, summary_writer, tag):
        Hook.__init__(self, summary_writer, tag)
        self._name = name
        self._data = data
        self._session_iterator = session_iterator
        self._sequence_iterator = sequence_iterator
        self._song_to_id = song_to_id

    # The implementation of this hook is very similar to training, except that train_op is not evaluated
    # because of course we're not trying to train the model, rather just evaluate it on some data set
    def __call__(self, session, model, train_loss, epoch):
        costs = 0.0

        for playlist in self._session_iterator(self._data, self._song_to_id, model.config.num_steps,
                                               model.config.batch_size):
            state = model.initial_state.eval()
            for step, (x, y, lengths) in enumerate(self._sequence_iterator(playlist, model.config.num_steps)):
                cost, state = session.run([model.cost, model.final_state],
                                          {model.input_data: x,
                                           model.targets: y,
                                           model.initial_state: state,
                                           model.actual_seq_lengths: lengths})
                costs += cost

        print("Epoch: %d %s Loss: %.3f" % (epoch, self._name, costs))
        self.update_summary(session, epoch, costs)


class EvaluationHook(Hook):
    def __init__(self, data, name, session_iterator, sequence_iterator, song_to_id, summary_writer, tag):
        Hook.__init__(self, summary_writer, tag)
        self._name = name
        self._data = data
        self._session_iterator = session_iterator
        self._sequence_iterator = sequence_iterator
        self._song_to_id = song_to_id

    def __call__(self, session, model, train_loss, epoch):
        # cost used in the actual model
        model_costs = 0.0
        eval_costs = {}
        K = [5]  # add more possibly

        for k_index, k in enumerate(K):
            shaped_targets = tf.reshape(model.targets, [model.config.batch_size * model.config.num_steps])
            top_k_op = tf.nn.in_top_k(model.prediction, shaped_targets, k)

            eval_costs[k_index] = 0.0
            step_count = 0

            for playlist in self._session_iterator(self._data, self._song_to_id, model.config.num_steps,
                                                   model.config.batch_size):

                state = model.initial_state.eval()

                for step, (x, y, lengths) in enumerate(self._sequence_iterator(playlist, model.config.num_steps)):
                    state, result = session.run([model.final_state, top_k_op],
                                                    {model.input_data: x,
                                                     model.targets: y,
                                                     model.initial_state: state,
                                                     model.actual_seq_lengths: lengths})

                    accuracy = float(result.astype(int).sum()) / len(result)  # Is this Precision@k? I'm not sure
                    step_count += 1
                    eval_costs[k_index] += accuracy
                    print("Step %s complete with cumulative evaluation cost %.3f" % (step, eval_costs[k_index]))

                    # model_costs += model_cost
                    # not sure if we need the model costs but could use it to compare with training
            print("Average accuracy for %d is %f" % (k, eval_costs[k_index]))

        print("Epoch: %d %s Loss: %.3f" % (epoch, self._name, eval_costs))
        self.update_summary(session, epoch, eval_costs)  # include eval cots in summary?
