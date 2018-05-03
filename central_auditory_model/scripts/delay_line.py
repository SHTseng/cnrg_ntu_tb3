import numpy as np
import warnings

class DelayLine(object):
    def __init__(self, data_dim, sample_rate, max_delay=1.0, initial_value=0.):
        self.data_dim = data_dim
        self.sample_rate = float(sample_rate)
        self.max_delay = max_delay
        self.buf_len = int(max_delay * sample_rate)
        self.buffer = initial_value * np.ones((self.buf_len,) + tuple(data_dim))
        self.buf_head = 0
        self.n_steps = 0

    def update(self, data):
        if data.shape[0] > self.buf_len:
            raise ValueError('buffer overflow: updating %d steps while buffer is only %d steps.' % (data.shape[0], self.buf_len))

        stop = self.buf_head + data.shape[0]
        wrapped_index = np.arange(self.buf_head, stop)
        wrapped_index[wrapped_index >= self.buf_len] -= self.buf_len
        self.buf_head = (stop - self.buf_len) if stop >= self.buf_len else stop

        self.buffer[wrapped_index] = data

        self.n_steps += data.shape[0]
        

    def delayed_view(self, delay):

        def view(t):
            steps_behind = self.n_steps - int((t - delay) * self.sample_rate)
            if steps_behind > self.buf_len:
                warnings.warn('Buffer already forgot!', Warning)
                return self.buffer[self.buf_head]
            elif steps_behind < 1:
                warnings.warn('Buffer is not there yet!', Warning)
                return self.buffer[self.buf_head - 1]
            else:
                index = self.buf_head - steps_behind
                index = index + self.buf_len if index < 0 else index
                return self.buffer[index]

        return view

    def batch_view_chunk(self, start_step, n_steps, delay_steps=[0]):
        delay_steps = np.array(delay_steps, dtype=np.int)        
        if not delay_steps.shape:
            raise ValueError('delay_steps must be an array-like.')

        if np.min(delay_steps) < 0:
            raise ValueError('delay_steps CAN\'T be negative.')

        steps_behind = self.n_steps - start_step

        if (steps_behind + np.max(delay_steps)) > self.buf_len:
            warnings.warn('Buffer already forgot! Abort.', Warning)
            return

        if steps_behind < n_steps:            
            if steps_behind > 0:
                n_steps = steps_behind
                warnings.warn('Buffer is not there yet! shrink n_steps to %d.' % n_steps, Warning)
            else:
                warnings.warn('Buffer is not there yet! Abort.', Warning)
                return        
        
        start = self.buf_head - steps_behind
        stop = start + n_steps
        wrapped_index = np.arange(start, stop)[np.newaxis, :] - delay_steps[:, np.newaxis]
        wrapped_index[wrapped_index >= self.buf_len] -= self.buf_len

        return self.buffer[wrapped_index]


if __name__ == '__main__':
    dl = DelayLine((10,), max_delay=1.0, sample_rate=100, initial_value=0.05)
    dl.update(np.arange(100)[:,np.newaxis] * 10 + np.arange(10))
    view = dl.delayed_view(0.)
    print 'view(-0.5)', view(-0.5)
    print 'view(0.)', view(0.)
    print 'view(0.1)', view(0.1)
    print 'view(0.5)', view(0.5)
    print 'view(1.0)', view(1.0)
    print 'view(1.5)', view(1.5)

    delays = [0, 1, 2]
    delays_rev = list(reversed(delays))

    print '*' * 40
    print dl.batch_view_chunk(0, 5, [0])
    print dl.batch_view_chunk(50, 5, delays)
    print dl.batch_view_chunk(50, 5, delays_rev)

