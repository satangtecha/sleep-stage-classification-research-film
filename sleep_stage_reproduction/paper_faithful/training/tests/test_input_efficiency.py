import gc
import unittest
import weakref

import numpy as np

from paper_faithful.training.splits import EpochMember
from paper_faithful.training.trainer import CacheSequence


class Entry:
 def __init__(self,offset,label):self.offset,self.label=offset,label


class CountingCache:
 def __init__(self,shards):
  self.shards=shards;self.array_calls=0
 def entry(self,member,route):return Entry(0,member.epoch_index+10)
 def array(self,entry):
  self.array_calls+=1;return self.shards[entry.label-10]


class InputEfficiencyTests(unittest.TestCase):
 def members(self,count):return tuple(EpochMember("S","R",index) for index in range(count))
 def test_flat_values_boundaries_remainder_and_cached_window_metadata(self):
  shards=[np.arange(3*2*2,dtype=np.float64).reshape(1,3,2,2)+100*index for index in range(3)]
  cache=CountingCache(shards);sequence=CacheSequence(cache,self.members(3),"route",2,drop_remainder=False)
  self.assertEqual(cache.array_calls,1)
  self.assertEqual((len(sequence),len(sequence)),(5,5));self.assertEqual(cache.array_calls,1)
  x0,y0=sequence[0];x4,y4=sequence[4]
  expected=np.concatenate([shard[0] for shard in shards],axis=0)
  np.testing.assert_array_equal(np.concatenate((x0,sequence[1][0],sequence[2][0],sequence[3][0],x4)),expected)
  self.assertEqual(x0.dtype,np.float32);self.assertEqual(y0.dtype,np.int32)
  self.assertEqual(np.concatenate((y0,sequence[1][1],sequence[2][1],sequence[3][1],y4)).tolist(),[10,10,10,11,11,11,12,12,12])
  self.assertEqual(x4.shape[0],1);self.assertEqual(y4.tolist(),[12])
  dropped=CacheSequence(CountingCache(shards),self.members(3),"route",2,drop_remainder=True,nominal_batch=4)
  self.assertEqual(len(dropped),4)
  with self.assertRaises(IndexError):dropped[4]
  with self.assertRaises(IndexError):sequence[-1]
 def test_sequence_values_and_corruption_propagate(self):
  shards=[np.arange(2*2*2*2,dtype=np.float32).reshape(2,2,2,2)+100*index for index in range(3)]
  cache=CountingCache(shards);sequence=CacheSequence(cache,self.members(3),"route",2,sequence=True,drop_remainder=False)
  x,y=sequence[1]
  np.testing.assert_array_equal(x,np.stack((shards[2][0],)))
  self.assertEqual(y.tolist(),[12])
  class CorruptCache(CountingCache):
   def array(self,entry):
    if entry.label==11:raise OSError("corrupt shard")
    return super().array(entry)
  corrupt=CacheSequence(CorruptCache(shards),self.members(3),"route",2,drop_remainder=False)
  with self.assertRaisesRegex(OSError,"corrupt shard"):corrupt[1]
 def test_samples_are_copied_before_another_shard_view_is_read(self):
  class EphemeralViewCache:
   def __init__(self):
    self.shards=[np.full((1,2,1),index,dtype=np.float32) for index in range(3)];self.previous=None
   def entry(self,member,route):return Entry(0,member.epoch_index)
   def array(self,entry):
    gc.collect()
    if self.previous is not None:self.assert_previous_released()
    view=self.shards[entry.label].view();self.previous=weakref.ref(view);return view
   def assert_previous_released(self):
    if self.previous() is not None:raise AssertionError("prior shard view was retained")
  cache=EphemeralViewCache();sequence=CacheSequence(cache,self.members(3),"route",6,drop_remainder=False)
  x,_=sequence[0]
  self.assertFalse(any(np.shares_memory(x,shard) for shard in cache.shards))
  np.testing.assert_array_equal(x[:,0],np.array([0,0,1,1,2,2],dtype=np.float32))


if __name__=="__main__":unittest.main()
