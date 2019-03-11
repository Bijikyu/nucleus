// Protocol Buffers - Google's data interchange format
// Copyright 2018 Google LLC.  All rights reserved.
// https://developers.google.com/protocol-buffers/
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are
// met:
//
//     * Redistributions of source code must retain the above copyright
// notice, this list of conditions and the following disclaimer.
//     * Redistributions in binary form must reproduce the above
// copyright notice, this list of conditions and the following disclaimer
// in the documentation and/or other materials provided with the
// distribution.
//     * Neither the name of Google Inc. nor the names of its
// contributors may be used to endorse or promote products derived from
// this software without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
// "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
// LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
// A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
// OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
// SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
// LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
// DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
// THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

#include <Python.h>
#include <stdio.h>

#include "google/protobuf/pyext/message.h"
#include "python/google/protobuf/proto_api.h"

#include "google/protobuf/message_lite.h"

#include "nucleus/protos/bed.pb.h"
#include "nucleus/protos/bedgraph.pb.h"
#include "nucleus/protos/cigar.pb.h"
#include "nucleus/protos/fasta.pb.h"
#include "nucleus/protos/fastq.pb.h"
#include "nucleus/protos/gff.pb.h"
#include "nucleus/protos/position.pb.h"
#include "nucleus/protos/range.pb.h"
#include "nucleus/protos/reads.pb.h"
#include "nucleus/protos/reference.pb.h"
#include "nucleus/protos/struct.pb.h"
#include "nucleus/protos/variants.pb.h"
#include "nucleus/protos/feature.pb.h"
#include "nucleus/protos/example.pb.h"

namespace {

// C++ API.  Clients get at this via proto_api.h
struct ApiImplementation : google::protobuf::python::PyProto_API {
  const google::protobuf::Message*
      GetMessagePointer(PyObject* msg) const override {
    return google::protobuf::python::PyMessage_GetMessagePointer(msg);
  }
  google::protobuf::Message*
      GetMutableMessagePointer(PyObject* msg) const override {
    return google::protobuf::python::PyMessage_GetMutableMessagePointer(msg);
  }
};

}  // namespace

static PyObject* GetPythonProto3PreserveUnknownsDefault(
    PyObject* /*m*/, PyObject* /*args*/) {
  if (google::protobuf::internal::GetProto3PreserveUnknownsDefault()) {
    Py_RETURN_TRUE;
  } else {
    Py_RETURN_FALSE;
  }
}

static PyObject* SetPythonProto3PreserveUnknownsDefault(
    PyObject* /*m*/, PyObject* arg) {
  if (!arg || !PyBool_Check(arg)) {
    PyErr_SetString(
        PyExc_TypeError,
        "Argument to SetPythonProto3PreserveUnknownsDefault must be boolean");
    return NULL;
  }
  google::protobuf::internal::SetProto3PreserveUnknownsDefault(PyObject_IsTrue(arg));
  Py_RETURN_NONE;
}

static const char module_docstring[] =
"python-proto2 is a module that can be used to enhance proto2 Python API\n"
"performance.\n"
"\n"
"It provides access to the protocol buffers C++ reflection API that\n"
"implements the basic protocol buffer functions.";

static PyMethodDef ModuleMethods[] = {
  {"SetAllowOversizeProtos",
    (PyCFunction)google::protobuf::python::cmessage::SetAllowOversizeProtos,
    METH_O, "Enable/disable oversize proto parsing."},
  // DO NOT USE: For migration and testing only.
  {"GetPythonProto3PreserveUnknownsDefault",
    (PyCFunction)GetPythonProto3PreserveUnknownsDefault,
    METH_NOARGS, "Get Proto3 preserve unknowns default."},
  // DO NOT USE: For migration and testing only.
  {"SetPythonProto3PreserveUnknownsDefault",
    (PyCFunction)SetPythonProto3PreserveUnknownsDefault,
    METH_O, "Enable/disable proto3 unknowns preservation."},
  { NULL, NULL}
};

#if PY_MAJOR_VERSION >= 3
static struct PyModuleDef _module = {
  PyModuleDef_HEAD_INIT,
  "_message",
  module_docstring,
  -1,
  ModuleMethods,  /* m_methods */
  NULL,
  NULL,
  NULL,
  NULL
};
#define INITFUNC PyInit__message
#define INITFUNC_ERRORVAL NULL
#else  // Python 2
#define INITFUNC init_message
#define INITFUNC_ERRORVAL
#endif

extern "C" {
  PyMODINIT_FUNC INITFUNC(void) {
    PyObject* m;
#if PY_MAJOR_VERSION >= 3
    m = PyModule_Create(&_module);
#else
    m = Py_InitModule3("_message", ModuleMethods,
                       module_docstring);
#endif
    if (m == NULL) {
      return INITFUNC_ERRORVAL;
    }

    if (!google::protobuf::python::InitProto2MessageModule(m)) {
      Py_DECREF(m);
      return INITFUNC_ERRORVAL;
    }

    // Adds the C++ API
    if (PyObject* api =
            PyCapsule_New(new ApiImplementation(),
                          google::protobuf::python::PyProtoAPICapsuleName(), NULL)) {
      PyModule_AddObject(m, "proto_API", api);
    } else {
      return INITFUNC_ERRORVAL;
    }

    nucleus::genomics::v1::BedGraphRecord().descriptor();
    nucleus::genomics::v1::BedRecord().descriptor();
    nucleus::genomics::v1::BedHeader().descriptor();
    nucleus::genomics::v1::BedReaderOptions().descriptor();
    nucleus::genomics::v1::BedWriterOptions().descriptor();
    nucleus::genomics::v1::CigarUnit().descriptor();
    nucleus::genomics::v1::FastaRecord().descriptor();
    nucleus::genomics::v1::FastaReaderOptions().descriptor();
    nucleus::genomics::v1::FastaWriterOptions().descriptor();
    nucleus::genomics::v1::FastqRecord().descriptor();
    nucleus::genomics::v1::FastqReaderOptions().descriptor();
    nucleus::genomics::v1::FastqWriterOptions().descriptor();
    nucleus::genomics::v1::GffRecord().descriptor();
    nucleus::genomics::v1::GffHeader().descriptor();
    nucleus::genomics::v1::GffReaderOptions().descriptor();
    nucleus::genomics::v1::GffWriterOptions().descriptor();
    nucleus::genomics::v1::Position().descriptor();
    nucleus::genomics::v1::Range().descriptor();
    nucleus::genomics::v1::LinearAlignment().descriptor();
    nucleus::genomics::v1::Read().descriptor();
    nucleus::genomics::v1::SamHeader().descriptor();
    nucleus::genomics::v1::ReadGroup().descriptor();
    nucleus::genomics::v1::Program().descriptor();
    nucleus::genomics::v1::SamReaderOptions().descriptor();
    nucleus::genomics::v1::ReadRequirements().descriptor();
    nucleus::genomics::v1::ContigInfo().descriptor();
    nucleus::genomics::v1::ReferenceSequence().descriptor();
    nucleus::genomics::v1::Struct().descriptor();
    nucleus::genomics::v1::Value().descriptor();
    nucleus::genomics::v1::ListValue().descriptor();
    nucleus::genomics::v1::Variant().descriptor();
    nucleus::genomics::v1::VariantCall().descriptor();
    nucleus::genomics::v1::VcfHeader().descriptor();
    nucleus::genomics::v1::VcfFilterInfo().descriptor();
    nucleus::genomics::v1::VcfInfo().descriptor();
    nucleus::genomics::v1::VcfFormatInfo().descriptor();
    nucleus::genomics::v1::VcfStructuredExtra().descriptor();
    nucleus::genomics::v1::VcfExtra().descriptor();
    nucleus::genomics::v1::VcfReaderOptions().descriptor();
    nucleus::genomics::v1::VcfWriterOptions().descriptor();
    tensorflow::Example().descriptor();
    tensorflow::SequenceExample().descriptor();
    tensorflow::BytesList().descriptor();
    tensorflow::FloatList().descriptor();
    tensorflow::Int64List().descriptor();
    tensorflow::Feature().descriptor();
    tensorflow::Features().descriptor();
    tensorflow::FeatureList().descriptor();
    tensorflow::FeatureLists().descriptor();

#if PY_MAJOR_VERSION >= 3
    return m;
#endif
  }
}
