"""Small install-contract adapter around the maintained py_wheel producer.

rules_python's regular_file_mode is uniform, so it cannot express the legacy
scripts/SSD executable exceptions. Metadata and wheel production stay upstream.
"""

load("@rules_python//python:packaging.bzl", "PyWheelInfo", "py_wheel")

def _install_contract_impl(ctx):
    original = ctx.attr.wheel[PyWheelInfo]
    output = ctx.actions.declare_file(ctx.label.name + "/" + original.wheel.basename)
    ctx.actions.run(
        executable = ctx.executable._tool,
        inputs = [original.wheel],
        outputs = [output],
        arguments = [original.wheel.path, output.path],
        mnemonic = "UtilitiesWheelInstallContract",
    )
    return [
        DefaultInfo(files = depset([output]), runfiles = ctx.runfiles(files = [output])),
        PyWheelInfo(wheel = output, name_file = original.name_file),
    ]

_install_contract = rule(
    implementation = _install_contract_impl,
    attrs = {
        "wheel": attr.label(mandatory = True, providers = [PyWheelInfo]),
        "_tool": attr.label(default = "//bazel:wheel_install_contract", executable = True, cfg = "exec"),
    },
)

def utilities_wheel(name, **kwargs):
    """Use native metadata/mode support, then preserve executable exceptions."""
    py_wheel(name = name + "_unadjusted", regular_file_mode = "0644", visibility = ["//visibility:private"], **kwargs)
    _install_contract(name = name, wheel = ":" + name + "_unadjusted")
