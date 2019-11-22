# Copyright 2019 Google LLC.
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

# Lint as: python3
"""Tests for nucleus.util.vis."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import glob
import os
from absl.testing import absltest
from absl.testing import parameterized
import numpy as np

from nucleus.protos import variants_pb2
from nucleus.testing import test_utils
from nucleus.util import vis
# pylint: disable=g-direct-tensorflow-import
from nucleus.protos import example_pb2
from nucleus.protos import feature_pb2


def _bytes_feature(list_of_strings):
  """Returns a bytes_list from a list of string / byte."""
  return feature_pb2.Feature(
      bytes_list=feature_pb2.BytesList(value=list_of_strings))


def _int_feature(list_of_ints):
  """Returns a int64_list from a list of int / bool."""
  return feature_pb2.Feature(
      int64_list=feature_pb2.Int64List(value=list_of_ints))


def _image_array(shape):
  return np.random.randint(255, size=shape, dtype=np.uint8)


def _mock_example_with_image(shape):
  arr = _image_array(shape)
  feature = {
      "image/encoded": _bytes_feature([arr.tobytes()]),
      "image/shape": _int_feature(shape)
  }
  return arr, example_pb2.Example(
      features=feature_pb2.Features(feature=feature))


def _mock_example_with_variant_and_alt_allele_indices(
    encoded_indices=b"\n\x01\x00", alleles=("A", "C")):
  variant = test_utils.make_variant(chrom="X", alleles=alleles, start=10)
  feature = {
      "variant/encoded": _bytes_feature([variant.SerializeToString()]),
      "alt_allele_indices/encoded": _bytes_feature([encoded_indices])
  }
  return example_pb2.Example(features=feature_pb2.Features(feature=feature))


class VisTest(parameterized.TestCase):

  def test_get_image_array_from_example(self):
    shape = (3, 2, 4)
    arr, example = _mock_example_with_image(shape)
    decoded_image_array = vis.get_image_array_from_example(example)
    self.assertTrue((arr == decoded_image_array).all())

  @parameterized.parameters(((5, 4, 3),), ((10, 7, 5),))
  def test_split_3d_array_into_channels(self, input_shape):
    arr = np.random.random(input_shape)
    output = vis.split_3d_array_into_channels(arr)
    self.assertLen(output, input_shape[2])
    for i in range(input_shape[2]):
      self.assertEqual(output[i].shape, arr.shape[0:2])
      self.assertTrue((output[i] == arr[:, :, i]).all())

  def test_channels_from_example(self):
    shape = (3, 2, 4)
    arr, example = _mock_example_with_image(shape)
    channels = vis.channels_from_example(example)
    self.assertLen(channels, shape[2])
    self.assertTrue((channels[0] == arr[:, :, 0]).all())

  @parameterized.parameters(((4, 8), (4, 8, 3)), ((100, 20), (100, 20, 3)))
  def test_convert_6_channels_to_rgb(self, input_shape, expected_output_shape):
    channels = [np.random.random(input_shape) for _ in range(6)]
    rgb = vis.convert_6_channels_to_rgb(channels)
    self.assertEqual(rgb.shape, expected_output_shape)

  @parameterized.parameters((None,), ("rgb",))
  def test_draw_deepvariant_pileup_with_example_input(self, composite_type):
    _, example = _mock_example_with_image((100, 10, 7))
    # Testing that it runs without error
    vis.draw_deepvariant_pileup(example=example, composite_type=composite_type)

  @parameterized.parameters((None,), ("rgb",))
  def test_draw_deepvariant_pileup_with_channels_input(self, composite_type):
    channels = [_image_array((100, 221)) for _ in range(6)]
    # Testing that it runs without error
    vis.draw_deepvariant_pileup(
        channels=channels, composite_type=composite_type)

  @parameterized.parameters(
      ([[0.0, 1], [5, 10]], 0, 10, [[0, 25], [127, 255]]),
      ([[0.0, 0.1], [0.5, 1]], 0, 1, [[0, 25], [127, 255]]),
      ([[0.0, 0.1], [0.5, 1]], 0, 0.5, [[0, 51], [255, 255]]),
      ([[0.0, 0.1], [0.5, 1]], 0.5, 1, [[0, 0], [0, 255]]),
      ([[0.0, 0.1], [0.5, 1]], -1, 1, [[127, 140], [191, 255]]),
      ([[0.0, 0.1], [0.5, 1]], -1, 2, [[85, 93], [127, 170]]))
  def test_adjust_colors_for_png(self, arr, vmin, vmax, expected):
    arr = np.array(arr)
    scaled = vis.adjust_colors_for_png(arr, vmin=vmin, vmax=vmax)
    self.assertTrue((scaled == expected).all())

  @parameterized.parameters(((1, 5), 10, (10, 50)), ((1, 5), 20, (20, 100)))
  def test_enlarge_image_array(self, shape, scale, expected_output_shape):
    arr = np.random.random(shape)
    larger = vis.enlarge_image_array(arr, scale=scale)
    self.assertEqual(larger.shape, expected_output_shape)

  @parameterized.parameters(
      ((100, 200), "L"),
      ((100, 200, 3), "RGB"),
  )
  def test_scale_array_for_image(self, shape, expected_image_mode):
    arr = np.random.random(shape)
    scaled, image_mode = vis.scale_array_for_image(arr)
    # original array should be unchanged
    self.assertLess(np.max(arr), 1)
    self.assertNotEqual(arr.dtype, np.uint8)
    # output has been scaled up and its type changed
    self.assertGreater(np.max(scaled), 1)
    self.assertEqual(scaled.dtype, np.uint8)
    self.assertEqual(image_mode, expected_image_mode)

  @parameterized.parameters(
      ((100, 200), "L"),
      ((10, 1), "L"),
      ((100, 200, 3), "RGB"),
      ((10, 1, 3), "RGB"),
      ((100, 200, 6), None),
      ((100, 200, 3, 1), None),
      ((100), None),
  )
  def test_get_image_type_from_array(self, shape, expected):
    arr = _image_array(shape)
    if expected is not None:
      self.assertEqual(vis._get_image_type_from_array(arr), expected)
    else:
      self.assertRaisesWithPredicateMatch(
          ValueError, lambda x: str(x).index("dimensions") != -1,
          vis.save_to_png, arr)

  @parameterized.parameters(
      ((100, 200, 3), True),
      ((100, 200), True),
      ((100, 200, 6), False),
      ((100, 200, 3, 1), False),
      ((100), False),
  )
  def test_save_to_png(self, shape, should_succeed):
    arr = _image_array(shape)

    if should_succeed:
      temp_dir = self.create_tempdir().full_path
      output_path = os.path.join(temp_dir, "test.png")
      # check the file doesn't already exist before function runs
      self.assertEmpty(glob.glob(output_path))
      vis.save_to_png(arr, path=output_path)
      self.assertLen(glob.glob(output_path), 1)
    else:
      self.assertRaisesWithPredicateMatch(
          ValueError, lambda x: str(x).index("dimensions") != -1,
          vis.save_to_png, arr)

  @parameterized.parameters(
      ((100, 200, 3), True),
      ((100, 200), True),
      ((100, 200, 6), False),
      ((100, 200, 3, 1), False),
      ((100), False),
  )
  def test_array_to_png_works_with_floats(self, shape, should_succeed):
    arr = np.random.random(shape)

    if should_succeed:
      temp_dir = self.create_tempdir().full_path
      output_path = os.path.join(temp_dir, "test.png")
      # check the file doesn't already exist before function runs
      self.assertEmpty(glob.glob(output_path))
      vis.array_to_png(arr, path=output_path)
      self.assertLen(glob.glob(output_path), 1)
    else:
      self.assertRaisesWithPredicateMatch(
          ValueError, lambda x: str(x).index("dimensions") != -1,
          vis.array_to_png, arr)

  def test_variant_from_example(self):
    example = _mock_example_with_variant_and_alt_allele_indices()
    variant = vis.variant_from_example(example)
    self.assertIsInstance(variant, variants_pb2.Variant)

  @parameterized.parameters(
      (b"\n\x01\x00", [0]),
      (b"\n\x02\x00\x01", [0, 1]),
  )
  def test_alt_allele_indices_from_example(self, encoded_indices, expected):
    example = _mock_example_with_variant_and_alt_allele_indices(encoded_indices)
    indices = vis.alt_allele_indices_from_example(example)
    self.assertEqual(indices, expected)

  @parameterized.parameters(
      ("chr1", 100, "G", "chr1:100_G"),
      ("X", 0, "GACGT", "X:0_GACGT"),
  )
  def test_locus_id_from_variant(self, chrom, pos, ref, expected):
    variant = test_utils.make_variant(
        chrom=chrom, alleles=[ref, "A"], start=pos)
    locus_id = vis.locus_id_from_variant(variant)
    self.assertEqual(locus_id, expected)

  @parameterized.parameters(
      (b"\n\x01\x00", ["A", "G", "GA", "AG"], "G"),
      (b"\n\x02\x00\x01", ["C", "CA", "T", "TA"], "CA-T"),
      (b"\n\x02\x01\x02", ["C", "CA", "T", "TA"], "T-TA"),
  )
  def test_alt_from_example(self, encoded_indices, alleles, expected):
    example = _mock_example_with_variant_and_alt_allele_indices(
        encoded_indices=encoded_indices, alleles=alleles)
    alt = vis.alt_from_example(example)
    self.assertEqual(alt, expected)

  @parameterized.parameters(
      (b"\n\x01\x00", ["A", "G", "GA", "AG"], "X:10_A_G"),
      (b"\n\x02\x00\x01", ["C", "CA", "T", "TA"], "X:10_C_CA-T"),
      (b"\n\x02\x01\x02", ["C", "CA", "T", "TA"], "X:10_C_T-TA"),
  )
  def test_locus_id_with_alt(self, encoded_indices, alleles, expected):
    example = _mock_example_with_variant_and_alt_allele_indices(
        encoded_indices=encoded_indices, alleles=alleles)
    locus_id_with_alt = vis.locus_id_with_alt(example)
    self.assertEqual(locus_id_with_alt, expected)

  @parameterized.parameters(
      ([0], ["C"], "C"),
      ([0, 1], ["C", "TT"], "C-TT"),
      ([3, 4], ["C", "TT", "T", "G", "A"], "G-A"),
  )
  def test_alt_bases_from_indices(self, indices, alternate_bases, expected):
    alt = vis.alt_bases_from_indices(indices, alternate_bases)
    self.assertEqual(alt, expected)


if __name__ == "__main__":
  absltest.main()
