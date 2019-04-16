import collections
import os
import pickle
import numpy as np
from pyflann import FLANN
# ngtpy is buggy. (incremental remove and add is fragile)
#import ngtpy

class FastDictionary(object):
    def __init__(self,maxlen):
        self.flann = FLANN()

        self.counter = 0

        self.contents_lookup = {} #{oid: (e,q)}
        self.p_queue = collections.deque() #priority queue contains; list of (priotiry_value,oid)
        self.maxlen = maxlen

    def save(self,dir,fname,it=None):
        fname = f'{fname}' if it is None else f'{fname}-{it}'

        with open(os.path.join(dir,fname),'wb') as f:
            pickle.dump((self.contents_lookup,self.p_queue,self.maxlen),f)

    def restore(self,fname):
        with open(fname,'rb') as f:
            _contents_lookup, _p_queue, maxlen = pickle.load(f)

            assert self.maxlen == maxlen, (self.maxlen,maxlen)

        new_oid_lookup = {}
        E = []
        for oid,(e,q) in _contents_lookup.items():
            E.append(e)

            new_oid, self.counter = self.counter, self.counter+1

            new_oid_lookup[oid] = new_oid
            self.contents_lookup[new_oid] = (e,q)

        # Rebuild KD-Tree
        self.flann.build_index(np.array(E))

        # Rebuild Heap
        while len(_p_queue) >= 0:
            oid = _p_queue.popleft()

            if not oid in new_oid_lookup:
                continue
            self.p_queue.append(new_oid_lookup[oid])

    def add(self,E,Contents):
        assert not np.isnan(E).any(), ('NaN Detected in Add',np.argwhere(np.isnan(E)))
        assert len(E) == len(Contents)

        if self.counter == 0:
            self.flann.build_index(E)
        else:
            self.flann.add_points(E)
        Oid, self.counter = np.arange(self.counter,self.counter+len(E)), self.counter + len(E)

        for oid,content in zip(Oid,Contents):
            self.contents_lookup[oid] = content
            self.p_queue.append(oid)

            if len(self.contents_lookup) > self.maxlen:
                while not self.p_queue[0] in self.contents_lookup:
                    self.p_queue.popleft() #invalidated items due to update, so just pop.

                old_oid = self.p_queue.popleft()

                self.flann.remove_point(old_oid)
                del self.contents_lookup[old_oid]

    def query_knn(self,E,K=100):
        assert not np.isnan(E).any(), ('NaN Detected in Querying',np.argwhere(np.isnan(E)))

        flatten = False
        if E.ndim == 1:
            E = E[None]
            flatten = True

        Oids, _ = self.flann.nn_index(E,num_neighbors=K)
        NN_E = np.zeros((len(E),K,E.shape[1]),np.float32)
        NN_Q = np.zeros((len(E),K),np.float32)

        for b,oids in enumerate(Oids):
            for k,oid in enumerate(oids):
                e,q = self.contents_lookup[oid]

                NN_E[b,k] = e
                NN_Q[b,k] = q

        if flatten:
            return Oids, NN_E[0], NN_Q[0]
        else:
            return Oids, NN_E, NN_Q

    def update(self,Oid,E,Contents):
        """
        Basically, same this is remove & add.
        This code only manages a heap more effectively; since delete an item in the middle of heap is not trivial!)
        """
        assert not np.isnan(E).any(), ('NaN Detected in Updating',np.argwhere(np.isnan(E)))
        assert len(np.unique(Oid)) == len(Oid)

        # add new Embeddings
        self.flann.add_points(E)
        NewOid, self.counter = np.arange(self.counter,self.counter+len(E)), self.counter + len(E)

        for oid,new_oid,content in zip(Oid,NewOid,Contents):
            self.contents_lookup[new_oid] = content
            self.p_queue.append(new_oid)

            # delete from kd-tree
            self.flann.remove_point(oid)
            # delete from contents_lookup
            del self.contents_lookup[oid]
            # I cannot remove from p_queue, but it will be handeled in add op.

if __name__ == "__main__":
    pass