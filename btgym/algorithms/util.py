
import numpy as np
import tensorflow as tf
from tensorflow.python.util.nest import flatten as flatten_nested
from tensorflow.python.util.nest import assert_same_structure
from tensorflow.contrib.rnn import LSTMStateTuple


def rnn_placeholders(state):
    """
    Given nested [multilayer] RNN state tensor, infers and returns state placeholders.

    Args:
        state:  tf.nn.lstm zero-state tuple.

    Returns:    tuple of placeholders
    """
    if isinstance(state, tf.contrib.rnn.LSTMStateTuple):
        c, h = state
        c = tf.placeholder(tf.float32, tf.TensorShape([None]).concatenate(c.get_shape()[1:]), c.op.name + '_c_pl')
        h = tf.placeholder(tf.float32, tf.TensorShape([None]).concatenate(h.get_shape()[1:]), h.op.name + '_h_pl')
        return tf.contrib.rnn.LSTMStateTuple(c, h)
    elif isinstance(state, tf.Tensor):
        h = state
        h = tf.placeholder(tf.float32, tf.TensorShape([None]).concatenate(h.get_shape()[1:]), h.op.name + '_h_pl')
        return h
    else:
        structure = [rnn_placeholders(x) for x in state]
        return tuple(structure)


def nested_placeholders(ob_space, batch_dim=None, name='nested'):
    """
    Given nested observation space as dictionary of shape tuples,
    returns nested state batch-wise placeholders.

    Args:
        ob_space:   [nested] dict of shapes
        name:       name scope
        batch_dim:  batch dimension
    Returns:
        nested dictionary of placeholders
    """
    if isinstance(ob_space,dict):
        out = {key: nested_placeholders(value, batch_dim, name + '_' + key) for key, value in ob_space.items()}
        return out
    else:
        out = tf.placeholder(tf.float32, [batch_dim] + list(ob_space), name + '_pl')
        return out


def flat_placeholders(ob_space, batch_dim=None, name='flt'):
    """
    Given nested observation space as dictionary of shape tuples,
    returns flattened dictionary of batch-wise placeholders.

    Args:
        ob_space:   [nested dict] of tuples
        name:       name_scope
        batch_dim:  batch dimension
    Returns:
        flat dictionary of tf.placeholders
    """
    return flatten_nested(nested_placeholders(ob_space, batch_dim=batch_dim, name=name))


def feed_dict_from_nested(placeholder, value, expand_batch=False):
    """
    Zips flat feed dictionary form nested dictionaries of placeholders and values.

    Args:
        placeholder:    nested dictionary of placeholders
        value:          nested dictionary of values
        expand_batch:   if true - add fake batch dimension to values

    Returns:
        flat feed_dict
    """
    assert_same_structure(placeholder, value, check_types=True)
    return _flat_from_nested(placeholder, value, expand_batch)


def _flat_from_nested(placeholder, value, expand_batch):
    feed_dict = {}
    if isinstance(placeholder, dict):
        for key in placeholder.keys():
            feed_dict.update(_flat_from_nested(placeholder[key], value[key], expand_batch))

    else:
        if expand_batch:
            feed_dict.update({placeholder: [value]})

        else:
            feed_dict.update({placeholder: value})

    return feed_dict


def feed_dict_rnn_context(placeholders, values):
    """
    Creates tf.feed_dict for flat placeholders and nested values.

    Args:
        placeholders:       flat structure of placeholders
        values:             nested structure of values

    Returns:
        flat feed dictionary
    """
    return {key: value for key, value in zip(placeholders, flatten_nested(values))}


def as_array(struct):
    """
    Given a dictionary of lists or tuples returns dictionary of np.arrays of same structure.

    Args:
        struct: dictionary of list, tuples etc.

    Returns:
        dict of np.arrays
    """
    if isinstance(struct,dict):
        out = {}
        for key, value in struct.items():
            out[key] = as_array(value)
        return out

    else:
        return np.asarray(struct)


def batch_concat(dict_list, _top=True):
    """
    Concatenates values of given processed rollouts
    along batch  dimension.

    Args:
        dict_list:   list of processed rollouts of the same size.

    Returns:
        dictionary of stacked arrays.
    """
    master = dict_list[0]
    batch = {}
    if _top:
        # Shape inference:
        batch['rnn_batch_size'] = len(dict_list)
        batch['rnn_time_steps'] = master['terminal'].shape[0]

    if isinstance(master, dict):
        for key in master.keys():
            value_list = [value[key] for value in dict_list]
            batch[key] = batch_concat(value_list, False)

    elif isinstance(master, LSTMStateTuple):
        c = batch_concat([state[0] for state in dict_list], False)
        h = batch_concat([state[1] for state in dict_list], False)
        batch = LSTMStateTuple(c=c, h=h)

    elif isinstance(master, tuple):
        batch = tuple([batch_concat([struct[i] for struct in dict_list], False) for i in range(len(master))])

    else:
        batch = np.concatenate(dict_list, axis=0)

    return batch


def _show_struct(struct):
    if isinstance(struct, dict):
        for key, value in struct.items():
            print(key)
            _show_struct(value)

    elif type(struct) in [LSTMStateTuple, tuple, list]:
        print('LSTM/tuple/list:', type(struct), len(struct))
        for i in struct:
            _show_struct(i)

    else:
        try:
            print('shape:', struct.shape)

        except AttributeError:
            print('value:', struct)
