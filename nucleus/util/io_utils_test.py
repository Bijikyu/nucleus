# Copyright 2018 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for nucleus.util.io_utils."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import types

from absl.testing import absltest
from absl.testing import parameterized
import mock

from nucleus.protos import reference_pb2
from nucleus.testing import test_utils
from nucleus.util import io_utils as io
from tensorflow.python.lib.io import python_io


class IOTest(parameterized.TestCase):

  @parameterized.parameters(
      # Unsharded outputs pass through as expected.
      dict(task_id=0, filespecs=['foo.txt'], expected=[0, 'foo.txt']),
      dict(
          task_id=0,
          filespecs=['foo.txt', 'bar.txt'],
          expected=[0, 'foo.txt', 'bar.txt']),
      dict(
          task_id=0,
          filespecs=['bar.txt', 'foo.txt'],
          expected=[0, 'bar.txt', 'foo.txt']),
      # It's ok to have False values for other bindings.
      dict(
          task_id=0, filespecs=['foo.txt', None], expected=[0, 'foo.txt',
                                                            None]),
      dict(task_id=0, filespecs=['foo.txt', ''], expected=[0, 'foo.txt', '']),
      dict(
          task_id=0,
          filespecs=['foo@10.txt', None],
          expected=[10, 'foo-00000-of-00010.txt', None]),
      dict(
          task_id=0,
          filespecs=['foo@10.txt', ''],
          expected=[10, 'foo-00000-of-00010.txt', '']),
      # Simple check that master behaves as expected.
      dict(
          task_id=0,
          filespecs=['foo@10.txt', None],
          expected=[10, 'foo-00000-of-00010.txt', None]),
      dict(
          task_id=0,
          filespecs=['foo@10', None],
          expected=[10, 'foo-00000-of-00010', None]),
      dict(
          task_id=1,
          filespecs=['foo@10', None],
          expected=[10, 'foo-00001-of-00010', None]),
      dict(
          task_id=9,
          filespecs=['foo@10', None],
          expected=[10, 'foo-00009-of-00010', None]),
      # Make sure we handle sharding of multiple filespecs.
      dict(
          task_id=0,
          filespecs=['foo@10', 'bar@10', 'baz@10'],
          expected=[
              10, 'foo-00000-of-00010', 'bar-00000-of-00010',
              'baz-00000-of-00010'
          ]),
      dict(
          task_id=9,
          filespecs=['foo@10', 'bar@10', 'baz@10'],
          expected=[
              10, 'foo-00009-of-00010', 'bar-00009-of-00010',
              'baz-00009-of-00010'
          ]),
  )
  def test_resolve_filespecs(self, task_id, filespecs, expected):
    self.assertEqual(io.resolve_filespecs(task_id, *filespecs), expected)

  @parameterized.parameters(
      # shard >= num_shards.
      (10, ['foo@10']),
      # shard > 0 but master isn't sharded.
      (1, ['foo']),
      # Inconsistent sharding.
      (0, ['foo@10', 'bad@11']),
      # master isn't sharded but bad is.
      (0, ['foo', 'bad@11']),
  )
  def test_resolve_filespecs_raises_with_bad_inputs(self, task_id, outputs):
    with self.assertRaises(ValueError):
      io.resolve_filespecs(task_id, *outputs)

  @parameterized.parameters(
      # Unsharded files work.
      ('foo.txt', ['foo.txt']),
      ('foo-00000-of-00010.txt', ['foo-00000-of-00010.txt']),
      # Sharded file patterns work.
      ('foo@3.txt', [
          'foo-00000-of-00003.txt', 'foo-00001-of-00003.txt',
          'foo-00002-of-00003.txt'
      ]),
      ('foo@3',
       ['foo-00000-of-00003', 'foo-00001-of-00003', 'foo-00002-of-00003']),
  )
  def test_maybe_generate_sharded_filenames(self, filespec, expected):
    self.assertEqual(io.maybe_generate_sharded_filenames(filespec), expected)

  def write_test_protos(self, filename):
    protos = [reference_pb2.ContigInfo(name=str(i)) for i in range(10)]
    path = test_utils.test_tmpfile(filename)
    io.write_tfrecords(protos, path)
    return protos, path

  @parameterized.parameters('foo.tfrecord', 'foo@2.tfrecord', 'foo@3.tfrecord')
  def test_read_write_tfrecords(self, filename):
    protos, path = self.write_test_protos(filename)

    # Create our generator of records from read_tfrecords.
    reader = io.read_tfrecords(path, reference_pb2.ContigInfo)

    # Make sure it's actually a generator.
    self.assertEqual(type(reader), types.GeneratorType)

    # Check the round-trip contents.
    if '@' in filename:
      # Sharded outputs are striped across shards, so order isn't preserved.
      self.assertCountEqual(protos, reader)
    else:
      self.assertEqual(protos, list(reader))

  @parameterized.parameters(
      ('foo.tfrecord', ''),
      ('foo.tfrecord.gz', 'GZIP'),
      (['foo.tfrecord', 'bar.tfrecord'], ''),
      (['foo.tfrecord.gz', 'bar.tfrecord.gz'], 'GZIP'),
  )
  def test_make_tfrecord_options(self, filenames, expected_compression_type):
    compression_type = python_io.TFRecordOptions.get_compression_type_string(
        io.make_tfrecord_options(filenames))
    self.assertEqual(compression_type, expected_compression_type)

  @parameterized.parameters(
      (['foo.tfrecord', 'bar.tfrecord.gz'],),
      (['foo.tfrecord', 'bar.tfrecord', 'baz.tfrecord.gz'],),
  )
  def test_make_tfrecord_options_with_bad_inputs(self, filenames):
    with self.assertRaisesRegexp(
        ValueError,
        'Incorrect value: {}. Filenames need to be all of the same type: '
        'either all with .gz or all without .gz'.format(','.join(filenames))):
      io.make_tfrecord_options(filenames)

  @parameterized.parameters((filename, max_records)
                            for max_records in [None, 0, 1, 3, 100]
                            for filename in ['foo.tfrecord', 'foo@2.tfrecord'])
  def test_read_tfrecords_max_records(self, filename, max_records):
    protos, path = self.write_test_protos(filename)

    # Create our generator of records from read_tfrecords.
    if max_records is None:
      expected_n = len(protos)
    else:
      expected_n = min(max_records, len(protos))
    actual = io.read_tfrecords(
        path, reference_pb2.ContigInfo, max_records=max_records)
    self.assertLen(list(actual), expected_n)

  @parameterized.parameters('foo.tfrecord', 'foo@2.tfrecord', 'foo@3.tfrecord')
  def test_shard_sorted_tfrecords(self, filename):
    protos, path = self.write_test_protos(filename)

    # Create our generator of records.
    key = lambda x: int(x.name)
    reader = io.read_shard_sorted_tfrecords(
        path, key=key, proto=reference_pb2.ContigInfo)

    # Make sure it's actually a generator.
    self.assertEqual(type(reader), types.GeneratorType)

    # Check the round-trip contents.
    contents = list(reader)
    self.assertEqual(protos, contents)
    self.assertEqual(contents, sorted(contents, key=key))

  @parameterized.parameters((filename, max_records)
                            for max_records in [None, 0, 1, 3, 100]
                            for filename in ['foo.tfrecord', 'foo@2.tfrecord'])
  def test_shard_sorted_tfrecords_max_records(self, filename, max_records):
    protos, path = self.write_test_protos(filename)

    if max_records is None:
      expected_n = len(protos)
    else:
      expected_n = min(max_records, len(protos))
    # Create our generator of records from read_tfrecords.
    actual = io.read_shard_sorted_tfrecords(
        path,
        key=lambda x: int(x.name),
        proto=reference_pb2.ContigInfo,
        max_records=max_records)
    self.assertLen(list(actual), expected_n)


class RawProtoWriterAdaptorTests(parameterized.TestCase):

  def setUp(self):
    self.proto1 = reference_pb2.ContigInfo(
        name='p1', n_bases=10, pos_in_fasta=0)
    self.proto2 = reference_pb2.ContigInfo(
        name='p2', n_bases=20, pos_in_fasta=1)
    self.protos = [self.proto1, self.proto2]

  @parameterized.parameters(
      dict(take_ownership=True),
      dict(take_ownership=False),
  )
  def test_adaptor_with_ownership(self, take_ownership):
    mock_writer = mock.MagicMock()
    adaptor = io.RawProtoWriterAdaptor(
        mock_writer, take_ownership=take_ownership)

    # Write out protos to our adaptor.
    with adaptor as enter_return_value:
      # Make sure that __enter__ returns the adaptor itself.
      self.assertIs(adaptor, enter_return_value)
      adaptor.write(self.proto1)
      adaptor.write(self.proto2)

    if take_ownership:
      # If we took ownership, mock_writer __enter__ and __exit__ should have
      # been called.
      mock_writer.__enter__.assert_called_once_with()
      test_utils.assert_called_once_workaround(mock_writer.__exit__)
    else:
      # If not, they shouldn't have been called.
      test_utils.assert_not_called_workaround(mock_writer.__enter__)
      test_utils.assert_not_called_workaround(mock_writer.__exit__)

    self.assertEqual(mock_writer.write.call_args_list,
                     [mock.call(r.SerializeToString()) for r in self.protos])


class ShardsTest(parameterized.TestCase):

  @parameterized.named_parameters(
      ('no_suffix', '/dir/foo/bar@3', '/dir/foo/bar', 3, ''),
      ('suffix-dot', '/dir/foo/bar@3.txt', '/dir/foo/bar', 3, '.txt'),
  )
  def testParseShardedFileSpec(self, spec, expected_basename,
                               expected_num_shards, expected_suffix):

    basename, num_shards, suffix = io.ParseShardedFileSpec(spec)
    self.assertEqual(basename, expected_basename)
    self.assertEqual(num_shards, expected_num_shards)
    self.assertEqual(suffix, expected_suffix)

  def testParseShardedFileSpecInvalid(self):
    self.assertRaises(io.ShardError, io.ParseShardedFileSpec, '/dir/foo/bar@0')

  @parameterized.named_parameters(
      ('no_suffix', '/dir/foo/bar@3', [
          '/dir/foo/bar-00000-of-00003', '/dir/foo/bar-00001-of-00003',
          '/dir/foo/bar-00002-of-00003'
      ]),
      ('suffix', '/dir/foo/bar@3.txt', [
          '/dir/foo/bar-00000-of-00003.txt', '/dir/foo/bar-00001-of-00003.txt',
          '/dir/foo/bar-00002-of-00003.txt'
      ]),
  )
  def testGenerateShardedFilenames(self, spec, expected):
    names = io.GenerateShardedFilenames(spec)
    self.assertEqual(names, expected)

  def testGenerateShardedFilenamesManyShards(self):
    names = io.GenerateShardedFilenames('/dir/foo/bar@100000')
    self.assertEqual(len(names), 100000)
    self.assertEqual(names[99999], '/dir/foo/bar-099999-of-100000')

  @parameterized.named_parameters(
      ('no_spec', '/dir/foo/bar'),
      ('zero_shards', '/dir/foo/bar@0'),
  )
  def testGenerateShardedFilenamesError(self, spec):
    self.assertRaises(io.ShardError, io.GenerateShardedFilenames, spec)

  @parameterized.named_parameters(
      ('basic', '/dir/foo/bar@3', True),
      ('suffix', '/dir/foo/bar@3,txt', True),
      ('many_shards', '/dir/foo/bar@123456', True),
      ('invalid_spec', '/dir/foo/bar@0', False),
      ('not_spec', '/dir/foo/bar', False),
  )
  def testIsShardedFileSpec(self, spec, expected):
    actual = io.IsShardedFileSpec(spec)
    self.assertEqual(actual, expected,
                      'io.IshShardedFileSpec({0}) is {1} expected {2}'.format(
                          spec, actual, expected))

  @parameterized.named_parameters(
      ('no_suffix', '/dir/foo/bar', 3, '', '/dir/foo/bar-?????-of-00003'),
      ('suffix', '/dir/foo/bar', 3, '.txt', '/dir/foo/bar-?????-of-00003.txt'),
      ('many', '/dir/foo/bar', 1234567, '.txt',
       '/dir/foo/bar-???????-of-1234567.txt'),
  )
  def testGenerateShardedFilePattern(self, basename, num_shards, suffix,
                                     expected):

    self.assertEqual(
        io.GenerateShardedFilePattern(basename, num_shards, suffix), expected)

  @parameterized.named_parameters(
      ('no_spec', '/dir/foo/bar', '/dir/foo/bar'),
      ('suffix', '/dir/foo/bar@3.txt', '/dir/foo/bar-?????-of-00003.txt'),
      ('no_suffix', '/dir/foo/bar@3', '/dir/foo/bar-?????-of-00003'),
      ('1000', '/dir/foo/bar@1000', '/dir/foo/bar-?????-of-01000'),
      ('many', '/dir/foo/bar@12345678', '/dir/foo/bar-????????-of-12345678'),
  )
  def testNormalizeToShardedFilePattern(self, spec, expected):
    self.assertEqual(expected, io.NormalizeToShardedFilePattern(spec))

  @parameterized.named_parameters(
      ('no_spec', 'no_spec', ['no_spec']),
      ('sharded', 'sharded@3', ['sharded-00000-of-00003',
                                'sharded-00001-of-00003',
                                'sharded-00002-of-00003']),
      ('wildcard1', '*.ext', ['cat.ext', 'dog.ext']),
      ('wildcard2', 'fo?bar', ['foobar']),
      ('comma_list', 'file1,file2,file3', ['file1', 'file2', 'file3']),
      ('mixed_list', 'mixed.*txt,mixed@1,mixed_file',
       ['mixed.1txt', 'mixed.2txt', 'mixed-00000-of-00001', 'mixed_file']),
      ('with_dups', 'with_dups*',
       ['with_dups.1txt', 'with_dups.2txt', 'with_dups-00000-of-00001',
        'with_dups']),
  )
  def testGlobListShardedFilePatterns(self, specs, expected_files):
    # First, create all expected_files so Glob will work later.
    expected_full_files = [test_utils.test_tmpfile(f, '')
                           for f in expected_files]
    # Create the full spec names. This one doesn't create the files.
    full_specs = ','.join(
        [test_utils.test_tmpfile(spec) for spec in specs.split(',')])
    self.assertEqual(sorted(set(expected_full_files)),
                     io.GlobListShardedFilePatterns(full_specs))

if __name__ == '__main__':
  absltest.main()
