/*
 * Copyright 2018 Google LLC.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */

#include "nucleus/io/indexed_fasta_reader.h"

#include <stdlib.h>
#include <algorithm>

#include "absl/strings/ascii.h"
#include "htslib/tbx.h"
#include "nucleus/io/hts_path.h"
#include "nucleus/io/reader_base.h"
#include "nucleus/protos/range.pb.h"
#include "nucleus/protos/reference.pb.h"
#include "nucleus/util/utils.h"
#include "tensorflow/core/lib/core/errors.h"
#include "tensorflow/core/lib/core/status.h"
#include "tensorflow/core/platform/logging.h"

namespace nucleus {

using nucleus::genomics::v1::Range;

namespace {
// Gets information about the contigs from the fai index faidx.
std::vector<nucleus::genomics::v1::ContigInfo> ExtractContigsFromFai(
    const faidx_t* faidx) {
  int n_contigs = faidx_nseq(faidx);
  std::vector<nucleus::genomics::v1::ContigInfo> contigs(n_contigs);
  for (int i = 0; i < n_contigs; ++i) {
    nucleus::genomics::v1::ContigInfo* contig = &contigs[i];
    const char* name = faidx_iseq(faidx, i);
    CHECK_NE(name, nullptr) << "Name of " << i << " contig in is null";
    contig->set_name(name);
    contig->set_description("");
    contig->set_n_bases(faidx_seq_len(faidx, name));
    CHECK_GE(contig->n_bases(), 0) << "Contig " << name << "Has < 0 bases";
    contig->set_pos_in_fasta(i);
  }
  return contigs;
}
}  // namespace

// Iterable class for traversing all Fasta records in the file.
class IndexedFastaReaderIterable : public GenomeReferenceRecordIterable {
 public:
  // Advance to the next record.
  StatusOr<bool> Next(GenomeReferenceRecord* out) override;

  // Constructor is invoked via IndexedFastaReader::Iterate.
  IndexedFastaReaderIterable(const IndexedFastaReader* reader);
  ~IndexedFastaReaderIterable() override;

 private:
  size_t pos_ = 0;
};

StatusOr<std::unique_ptr<IndexedFastaReader>> IndexedFastaReader::FromFile(
    const string& fasta_path, const string& fai_path, int cache_size_bases) {
  const string gzi = fasta_path + ".gzi";
  faidx_t* faidx =
      fai_load3_x(fasta_path.c_str(), fai_path.c_str(), gzi.c_str(), 0);
  if (faidx == nullptr) {
    return tensorflow::errors::NotFound(
        "could not load fasta and/or fai for fasta ", fasta_path);
  }
  return std::unique_ptr<IndexedFastaReader>(
      new IndexedFastaReader(fasta_path, faidx, cache_size_bases));
}

IndexedFastaReader::IndexedFastaReader(const string& fasta_path, faidx_t* faidx,
                                       int cache_size_bases)
    : fasta_path_(fasta_path),
      faidx_(faidx),
      contigs_(ExtractContigsFromFai(faidx)),
      cache_size_bases_(cache_size_bases),
      small_read_cache_(),
      cached_range_() {}

IndexedFastaReader::~IndexedFastaReader() {
  if (faidx_) {
    TF_CHECK_OK(Close());
  }
}

StatusOr<string> IndexedFastaReader::GetBases(const Range& range) const {
  if (faidx_ == nullptr) {
    return tensorflow::errors::FailedPrecondition(
        "can't read from closed IndexedFastaReader object.");
  }
  if (!IsValidInterval(range))
    return tensorflow::errors::InvalidArgument("Invalid interval: ",
                                               range.ShortDebugString());

  if (range.start() == range.end()) {
    // We are requesting an empty string. faidx_fetch_seq does not allow this,
    // so we have to special case it here.
    return string("");
  }

  bool use_cache = (cache_size_bases_ > 0) &&
                   (range.end() - range.start() <= cache_size_bases_);
  Range range_to_fetch;

  if (use_cache) {
    if (cached_range_ && RangeContains(*cached_range_, range)) {
      // Get from cache!
      string result = small_read_cache_.substr(
          range.start() - cached_range_->start(), range.end() - range.start());
      return result;
    } else {
      // Prepare to fetch a sizeable chunk from the FASTA.
      int64 contig_n_bases =
          Contig(range.reference_name()).ValueOrDie()->n_bases();
      range_to_fetch = MakeRange(
          range.reference_name(), range.start(),
          std::min(static_cast<int64>(range.start() + cache_size_bases_),
                   contig_n_bases));
      CHECK(IsValidInterval(range_to_fetch));
    }
  } else {
    range_to_fetch = range;
  }

  // According to htslib docs, faidx_fetch_seq c_name is the contig name,
  // start is the first base (zero-based) to include and end is the last base
  // (zero-based) to include. Len is an output variable returning the length
  // of the fetched region, -2 c_name not present, or -1 for a general error.
  // The returned pointer must be freed. We need to subtract one from our end
  // since end is exclusive in GenomeReference but faidx has an inclusive one.
  int len;
  char* bases =
      faidx_fetch_seq(faidx_, range_to_fetch.reference_name().c_str(),
                      range_to_fetch.start(), range_to_fetch.end() - 1, &len);
  if (len <= 0)
    return tensorflow::errors::InvalidArgument("Couldn't fetch bases for ",
                                               range.ShortDebugString());
  string result = absl::AsciiStrToUpper(bases);
  free(bases);

  if (use_cache) {
    // Update cache.
    small_read_cache_ = result;
    cached_range_ = range_to_fetch;
    // Return the requested substring.
    result = small_read_cache_.substr(0, range.end() - range.start());
  }
  return result;
}

StatusOr<std::shared_ptr<GenomeReferenceRecordIterable>>
IndexedFastaReader::Iterate() const {
  return StatusOr<std::shared_ptr<GenomeReferenceRecordIterable>>(
      MakeIterable<IndexedFastaReaderIterable>(this));
}

tensorflow::Status IndexedFastaReader::Close() {
  if (faidx_ == nullptr) {
    return tensorflow::errors::FailedPrecondition(
        "IndexedFastaReader already closed");
  } else {
    fai_destroy(faidx_);
    faidx_ = nullptr;
  }
  return tensorflow::Status::OK();
}

StatusOr<bool> IndexedFastaReaderIterable::Next(GenomeReferenceRecord* out) {
  TF_RETURN_IF_ERROR(CheckIsAlive());
  const IndexedFastaReader* fasta_reader =
      static_cast<const IndexedFastaReader*>(reader_);
  if (pos_ >= fasta_reader->contigs_.size()) {
    return false;
  }
  const genomics::v1::ContigInfo& contig = fasta_reader->contigs_.at(pos_);
  const string& reference_name = contig.name();
  out->first = reference_name;
  out->second =
      fasta_reader->GetBases(MakeRange(reference_name, 0, contig.n_bases()))
          .ValueOrDie();
  pos_++;
  return true;
}

IndexedFastaReaderIterable::~IndexedFastaReaderIterable() {}

IndexedFastaReaderIterable::IndexedFastaReaderIterable(
    const IndexedFastaReader* reader)
    : Iterable(reader) {}

}  // namespace nucleus
