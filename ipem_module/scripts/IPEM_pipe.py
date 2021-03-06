import os
import threading
import time
import subprocess


class IPEM_pipe:
    def __init__(self, channel_number=40, first_freq=2.0, freq_distance=0.5, sample_frequency=22050,
                 new_ani_callback=None, raw_ani_string=True, fifo_path='.'):
        self.channel_number = channel_number
        self.first_freq = first_freq
        self.freq_distance = freq_distance
        self.sample_frequency = sample_frequency
        self.new_ani_callback = new_ani_callback
        self.fifo_path = fifo_path
        self.pcm_name = 'ipem_pcm'
        self.ani_name = 'ipem_ani'
        self.pcm_fullpath = self.fifo_path + '/' + self.pcm_name
        self.ani_fullpath = self.fifo_path + '/' + self.ani_name

        try:
            os.makedirs(self.fifo_path)
        except OSError as oe:
            pass

        try:
            os.mkfifo(self.pcm_fullpath)
        except OSError as oe:
            pass

        try:
            os.mkfifo(self.ani_fullpath)
        except OSError as oe:
            pass

        def ani_receiver():
            with open(self.ani_fullpath, 'rb') as fifo_ani:
                print("%s opened" % self.ani_name)
                while True:
                    ani_str = fifo_ani.readline()
                    # print('READ(%d): %s' % (len(ani_str), ani_str))
                    if len(ani_str):
                        if raw_ani_string:
                            self.new_ani_callback(ani_str)
                        else:
                            print 'not implement yet'
                            # self.new_ani_callback(np_data)
                    else:
                        break

            print('"%s" closed' % self.ani_fullpath)

        self.ani_receiver_thread = threading.Thread(target=ani_receiver)
        # self.ani_receiver_thread.setDaemon(True)
        self.ani_receiver_thread.start()

        def ipem_process():          
            abspathname = os.path.abspath(os.path.dirname(__file__)) + '/'
            try:                
                t1 = time.time()
                log_str = subprocess.check_output([abspathname + 'IPEMAuditoryModelConsole',
                                                   '-nc', str(self.channel_number),
                                                   '-if', self.pcm_name,
                                                   '-id', self.fifo_path,
                                                   '-of', self.ani_name,
                                                   '-od', self.fifo_path,
                                                   '-fs', str(self.sample_frequency),
                                                   '-ff', 'pcm'])
                print log_str
                print 'subprocess returned in %f sec' % (time.time() - t1)
            except subprocess.CalledProcessError as e:
                print e

        self.ipem_process_thread = threading.Thread(target=ipem_process)
        # self.ipem_process_thread.setDaemon(True)
        self.ipem_process_thread.start()

        def pcm_feeder_generator():
            with open(self.pcm_fullpath, 'wb') as fifo_pcm:
                print("%s opened" % self.pcm_name)
                while True:
                    samples = yield
                    if samples is None:
                        print 'closing pcm_feeder due to close()'
                        return
                    try:
                        fifo_pcm.write(samples)
                        fifo_pcm.flush()
                    except IOError:
                        print 'closing pcm_feeder due to fifo IOError'
                        return

        self.pcm_feeder = pcm_feeder_generator()
        self.pcm_feeder.next()

    def feed_pcm_samples(self, samples):
        try:
            self.pcm_feeder.send(samples)
        except StopIteration:
            return False
        else:
            return True

    def close(self):
        try:
            self.pcm_feeder.send(None)
        except StopIteration:
            pass
        finally:
            print 'sent close signal to pcm_feeder.'


if __name__ == '__main__':
    def just_print(data):
        print data

    ipem_pipe = IPEM_pipe(new_ani_callback=just_print)
    ipem_pipe.feed_pcm_samples('test')
    ipem_pipe.feed_pcm_samples('test2')
    ipem_pipe.close()

