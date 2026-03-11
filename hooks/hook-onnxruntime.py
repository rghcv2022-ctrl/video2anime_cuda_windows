from PyInstaller.utils.hooks import collect_dynamic_libs

# Keep the package collection intentionally narrow.
# We only need the runtime C API pieces for inference.
binaries = collect_dynamic_libs('onnxruntime')

# Keep onnxruntime's Python package on disk in the frozen app instead of only inside PYZ.
# The native extension initialization is more reliable when the wheel-like package layout exists
# on the filesystem next to the collected capi binaries.
module_collection_mode = {
    'onnxruntime': 'py',
}

hiddenimports = [
    'onnxruntime.capi',
    'onnxruntime.capi._pybind_state',
    'onnxruntime.capi.onnxruntime_pybind11_state',
    'onnxruntime.capi.onnxruntime_inference_collection',
    'onnxruntime.capi.onnxruntime_validation',
]

excludedimports = [
    'onnxruntime.backend',
    'onnxruntime.datasets',
    'onnxruntime.quantization',
    'onnxruntime.tools',
    'onnxruntime.transformers',
]
