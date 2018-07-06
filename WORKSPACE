workspace(name = "nucleus")

# Abseil libraries
git_repository(
    name = "io_abseil_py",
    tag = "pypi-v0.2.2",
    remote = "https://github.com/abseil/abseil-py.git",
)
# Note: com_google_absl (the C++ abseil library) is provided by TensorFlow.

# CCTZ (Time-zone framework).
# TODO(b/80245980): transitive WORKSPACE dependency resolution doesn't
# work in bazel, so we need to include this to enable use of
# //absl/{time,synchronization}
http_archive(
    name = "com_googlesource_code_cctz",
    strip_prefix = "cctz-master",
    urls = ["https://github.com/google/cctz/archive/master.zip"],
)

# Note: we are using a post-1.6 build release that fixes a double-free.
new_http_archive(
    name = "htslib",
    build_file = "third_party/htslib.BUILD",
    sha256 = "7743e379fa27fdbaa81d4efc97adc5e0b2c5ade3cd09a93e311ea0c6b3a4ddf6",
    strip_prefix = "htslib-57fa9be5255475b2cf9331db32848590a8ea8eb9",
    urls = [
        "https://github.com/samtools/htslib/archive/57fa9be5255475b2cf9331db32848590a8ea8eb9.zip",
    ],
)

# Import tensorflow.  Note path.
local_repository(
    name = "org_tensorflow",
    path = "../tensorflow",
)

# Required boilerplate for tf_workspace(), apparently.
# This is copied from https://github.com/tensorflow/tensorflow/blob/v1.7.0/WORKSPACE.
http_archive(
    name = "io_bazel_rules_closure",
    sha256 = "6691c58a2cd30a86776dd9bb34898b041e37136f2dc7e24cadaeaf599c95c657",
    strip_prefix = "rules_closure-08039ba8ca59f64248bb3b6ae016460fe9c9914f",
    urls = [
        "https://mirror.bazel.build/github.com/bazelbuild/rules_closure/archive/08039ba8ca59f64248bb3b6ae016460fe9c9914f.tar.gz",
        "https://github.com/bazelbuild/rules_closure/archive/08039ba8ca59f64248bb3b6ae016460fe9c9914f.tar.gz",  # 2018-01-16
    ],
)

# We need a protobuf version at this hash or later because we need the API
# introduced in
# https://github.com/google/protobuf/pull/4698 with bug fix at
# https://github.com/google/protobuf/pull/4725
http_archive(
    name = "protobuf_archive",
    sha256 = "135d1105838932d04be79c06f429250531a73e699bd95aed83489aab9caa8622",
    strip_prefix = "protobuf-2efcec95b6d42e66ada2a14f3fbf38762c52641c",
    urls = [
        # TODO(thomaswc): Restore this URL when it is up on the mirror.
        # "https://mirror.bazel.build/github.com/google/protobuf/archive/a0e82dbe569552ac848d088391b63aaa1108d1a3.tar.gz",
        "https://github.com/cmclean/protobuf/archive/2efcec95b6d42e66ada2a14f3fbf38762c52641c.tar.gz",
    ],
)

# Import all of the tensorflow dependencies.
load("@org_tensorflow//tensorflow:workspace.bzl", "tf_workspace")

tf_workspace(tf_repo_name = "org_tensorflow")

new_local_repository(
    name = "clif",
    build_file = "third_party/clif.BUILD",
    path = "/usr/local",
)
