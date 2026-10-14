# Satellite Data Quality Inspector — MCP Project

## 1. Project overview

This project is a small **Model Context Protocol (MCP) server** for inspecting the quality of satellite-style scientific data. It gives an MCP-compatible AI assistant a controlled set of tools for examining NetCDF and HDF5 files, summarising numeric variables, interpreting quality flags, and reporting basic metadata.

The project is deliberately small and educational. It connects three ideas:

- **Scientific data handling:** satellite products commonly contain arrays, missing-value markers, scale factors, offsets, units, and quality flags.
- **Quality-control logic:** measurements should be checked using their metadata, not just by looking at raw numbers.
- **MCP tool access:** an AI application can call well-defined Python functions through an MCP server rather than needing direct access to arbitrary files or Python code.

The example dataset is synthetic. It is designed to exercise the workflow and is not a real satellite product or evidence of operational instrument performance.

## 2. What the project is intended to do

The server is intended to expose tools that let an MCP client ask questions such as:

- How many valid and missing measurements are in this variable?
- What are the minimum, maximum, and mean of a numeric field?
- What units and packing metadata are attached to the variable?
- How often does each quality-flag category occur?
- Are any flag values unrecognised by the metadata?
- Can a dataset inside an HDF5 file be inspected using the same basic checks?

The result is a compact, structured summary. It does **not** replace a full product-validation campaign, a scientific interpretation, or a mission-specific quality-control specification.

## 3. How the pieces fit together

The project separates responsibilities so that data-quality calculations can be tested independently from MCP communication.

### `create_sample.py`

Creates a small, repeatable NetCDF file under `data/`. The sample includes a brightness-temperature variable, a quality-flag variable, dimensions representing scanlines and pixels, and basic global metadata. A few brightness-temperature values are deliberately missing so that the quality checks have something to detect.

A fixed random seed is used so that the generated data is reproducible. This makes debugging and testing easier: repeated runs create equivalent synthetic input rather than a different random sample each time.

### `data/sample.nc`

The generated NetCDF file is the test input for the project. It contains:

- **Brightness temperature:** a two-dimensional floating-point array with units of kelvin.
- **Quality flag:** an integer array whose values represent categories such as good, suspect, and invalid.
- **Dimensions:** scanline and pixel axes that resemble the layout of an image-like satellite product.
- **Metadata:** descriptive attributes that help tools understand the variables.

The file is generated locally, so the project does not depend on downloading data from an external service.

### `quality.py`

Contains the scientific-quality functions. Keeping this logic separate from the server makes it possible to test the calculations directly with small arrays. It is also easier to reuse these functions later in scripts, notebooks, or a larger validation pipeline.

The core responsibilities are:

1. **Decode packed numeric values.** Identify fill or missing markers before applying scale factors and offsets. Convert valid raw values into physical values where packing metadata is present.
2. **Summarise numeric values.** Count total elements, valid elements, and missing or non-finite elements, then calculate simple statistics over valid values only.
3. **Summarise quality flags.** Use flag metadata to count the occurrences of each category and identify values that the metadata does not explain.

### `server.py`

Connects the scientific functions to MCP. It defines the tools an MCP client can discover and call. A tool accepts a small set of named inputs, invokes the relevant quality function, and returns a structured result that an AI application can explain to a user.

The server is also the right place to apply file-access restrictions. It should only allow inspection of intended data files inside the project's data directory, and should reject unsupported file types or paths outside that directory.

### `tests/test_quality.py`

Contains automated tests for the core calculations. The tests use small, known arrays and metadata so that the expected results can be calculated in advance. This helps detect regressions when the logic changes.

## 4. Why MCP is used

Without MCP, a user might run a Python script manually, inspect the output, and then ask an AI assistant to explain it. MCP standardises the connection between the AI application and the Python tools.

The typical interaction has four parts:

1. **MCP host:** the AI application in which the user asks a question.
2. **MCP client:** the component inside the host that communicates with the server.
3. **MCP server:** this project, which advertises available tools and executes their Python functions.
4. **Scientific libraries:** xarray, NumPy, h5py, and related packages that read data and perform calculations.

For example, a user may ask for a summary of the brightness-temperature variable. The host decides that a registered tool is appropriate, the client sends a structured request to the server, the server reads the permitted file and runs the quality logic, and the result is returned to the host for presentation.

MCP does not itself understand satellite physics or validate data. The scientific meaning comes from the Python functions, metadata, and validation rules implemented by the project.

## 5. Why these Python libraries are used

- **Python:** the main implementation language, with a large scientific-computing ecosystem.
- **MCP Python SDK:** exposes Python functions as tools that an MCP-compatible host can discover and invoke.
- **xarray:** represents labelled multi-dimensional scientific data and reads common NetCDF formats. Variable names, dimensions, and attributes remain accessible alongside the values.
- **NumPy:** provides efficient array operations, masks, finite-value checks, and statistics.
- **netCDF4 / h5netcdf:** provide NetCDF reading support through compatible backends. Which backend is used depends on the file and local installation.
- **h5py:** opens HDF5 files and accesses datasets by path when direct HDF5 inspection is required.
- **pytest:** runs the automated test suite and reports whether the expected behaviours hold.

A virtual environment is used to keep the project's dependencies separate from other Python projects. This reduces conflicts between packages and makes the environment easier to reproduce.

## 6. Setup and execution workflow

The following steps describe the intended workflow. Run commands from the project root directory, where `server.py` and `quality.py` are located.

### Step 1 — Create or enter the project directory

The project directory should contain the Python modules, a `data` directory, and a `tests` directory. Keeping the code and generated data in one project makes file access and testing easier to understand.

### Step 2 — Create and activate a virtual environment

Create a Python virtual environment for this project and activate it before installing packages or running tests. This helps ensure that the Python interpreter, package installer, and test runner all use the same environment.

If the terminal prompt shows more than one environment marker—for example, both a virtual environment and Conda's base environment—check which interpreter and test runner are actually being used. Mixing environments can cause confusing import errors.

### Step 3 — Install the dependencies

Install the MCP SDK, xarray, NumPy, NetCDF support, h5py, and pytest in the active environment. The exact dependency set can be refined later, but the packages should be installed in the same environment that will run the server and tests.

### Step 4 — Generate the synthetic NetCDF file

Run `create_sample.py` from the project root. The script creates the data directory if needed and writes the generated file to `data/sample.nc`.

This step is necessary because the repository's sample data is produced locally. If the file is missing, the server's tools will have no example input to inspect.

### Step 5 — Run the unit tests

Run the test suite with `python -m pytest -q` from the project root. Using `python -m pytest` helps ensure pytest is launched through the currently selected Python interpreter.

The initial test suite checks the following behaviours:

- Fill values are excluded before scale and offset are applied.
- NaN and infinite values do not contaminate ordinary summary statistics.
- Enumerated flags are counted according to their declared values and meanings.
- Bit-mask flags are handled according to their mask metadata.
- Inconsistent flag metadata is rejected rather than silently misinterpreted.

The expected initial outcome is five passing tests. If Python reports that it cannot import `quality`, first verify that `quality.py` exists in the project root and that the command is being run from that directory. Also check that the test runner belongs to the same Python environment as the project dependencies.

### Step 6 — Start the MCP server

Start the server using the entry point supported by the installed version of the MCP Python SDK. The SDK's API has evolved, so the server initialisation and launch method must match the version installed in the environment. If the server fails during import or startup, check the SDK version and its current API documentation rather than changing the scientific functions unnecessarily.

### Step 7 — Connect an MCP client or inspector

Use an MCP-compatible client or the MCP Inspector development tool to connect to the running server. Confirm that the server starts, the expected tools are listed, and each tool can be called with a valid file and variable name.

A successful Python test run proves that the quality functions work for the test cases. It does not by itself prove that MCP transport, tool discovery, or client configuration is working; those need to be checked separately.

### Step 8 — Try the tools with the sample file

Use `data/sample.nc` as the input and select the variable to inspect. Compare the returned counts and statistics with what is known about the synthetic data. For example, the brightness-temperature field deliberately contains two missing values, and the quality flags are generated from the three defined categories.

If the tool returns an error, determine whether it comes from file access, dataset reading, metadata interpretation, the quality calculation, or MCP request handling. Keeping these concerns separate makes the issue easier to isolate.

## 7. Important scientific decisions

### Missing values must be identified before unpacking

Some scientific products store measurements as integers to save space. Metadata can define a scale factor and an offset that convert stored values to physical units. A fill value is a special marker, not a real measurement.

Therefore, the correct order is to identify fill or missing markers in the raw representation, mark those entries as invalid, and apply the scale and offset only to valid entries. If a fill marker is scaled like an ordinary value, it can become an extreme but apparently valid measurement and distort the statistics.

### NaN and infinity are not valid ordinary measurements

Numeric arrays may contain NaN or positive/negative infinity. The summary function counts finite values as valid for its basic statistics and excludes non-finite values from minimum, maximum, and mean. A production system may need more nuanced rules for each product and variable.

### Metadata is part of the data

Units, scale factors, offsets, fill values, flag values, flag masks, and flag meanings help define how the data should be interpreted. Raw numeric values alone are not enough to determine scientific meaning.

The implementation deliberately rejects certain inconsistent flag metadata rather than guessing what the author intended. For operational products, it is preferable to report an ambiguity than to silently produce a misleading quality summary.

### Enumerated flags and bit-mask flags are different

An enumerated flag uses a set of specific values, each with a meaning. A bit-mask flag uses individual bits to represent conditions that may occur together. These representations require different counting logic and should not be treated as interchangeable.

Flag conventions vary between products. The implementation should be checked against the relevant product specification and applicable CF metadata conventions before it is used with real mission data.

## 8. What the tests demonstrate

The tests are intentionally small and deterministic. Each test isolates one behaviour:

| Test area | Why it matters |
|---|---|
| Fill values and unpacking | Prevents missing markers from becoming false physical measurements. |
| Finite-value statistics | Ensures NaN and infinity do not corrupt ordinary summary statistics. |
| Enumerated flags | Confirms counts for named categories match known input values. |
| Bit-mask flags | Checks that the individual condition masks are counted as intended. |
| Invalid metadata | Ensures contradictory or incomplete metadata produces an explicit error. |

Passing tests increases confidence in these specific behaviours. It does not guarantee that every possible NetCDF/HDF5 encoding, flag convention, corrupted file, or mission-specific rule is supported.

## 9. File access and security

A data-inspection tool should not accept unrestricted filesystem paths from an AI client. The server should resolve the requested path and confirm that the resulting file remains inside the configured data directory. It should also restrict supported formats and handle missing files, invalid dataset names, malformed metadata, and read errors cleanly.

This matters because an MCP server may be controlled through natural-language requests. File-path validation helps prevent a request from reading unrelated files on the computer. A file extension check alone is not a complete security boundary; path resolution and directory containment are also important.

The example project is intended for local learning. Before exposing the server to other users or networks, review its transport configuration, filesystem permissions, logging, dependency versions, and access controls.

## 10. Current limitations

This first version is a learning prototype, not an operational-grade satellite validation system. Important limitations include:

- The sample data is synthetic rather than drawn from a real mission product.
- Basic min/max/mean statistics do not establish scientific validity.
- Mission-specific thresholds and quality rules are not yet implemented.
- Full-array reads can consume too much memory for large products.
- HDF5 and NetCDF files may have different chunking, compression, dimension, and metadata conventions.
- Flag metadata conventions can be more complex than the initial examples.
- The MCP server API and launch commands must match the installed SDK version.
- Tool output should be checked for correct units, dimensions, and interpretation before it is used to support a scientific conclusion.

## 11. Recommended next improvements

A sensible development sequence is:

1. **Stabilise the environment and tests.** Record the Python and dependency versions and ensure the test suite runs consistently in a clean environment.
2. **Validate the MCP interface.** Check tool discovery, input validation, successful calls, and error responses through an MCP inspector or compatible host.
3. **Add product-specific rules.** Support valid ranges, mission thresholds, required metadata, and documented flag interpretations where the product specification defines them.
4. **Support large files safely.** Read data in chunks or slices and accumulate counts, minima, maxima, and sums without loading a complete multi-gigabyte variable into memory.
5. **Improve diagnostics.** Return clear information about the file, variable, dimensions, units, metadata used, and any warnings or assumptions.
6. **Add integration tests.** Test the server tools against the generated file, not only the helper functions.
7. **Try a real, non-sensitive sample product.** Compare the tool output with a trusted reader or existing validation procedure before extending to operational datasets.
8. **Produce a structured quality report.** Combine variable statistics, missing-data fractions, flag distributions, metadata checks, and warnings into one concise report.

## 12. How this relates to satellite IV&V work

The project illustrates a small part of a broader verification and validation workflow. It can automate repeatable checks on product contents and metadata, help identify unexpected missing data or flag distributions, and provide structured evidence for an engineer to investigate.

In an operational environment, these checks would be tied to requirements and acceptance criteria. Results would need traceability to the product version, processing configuration, auxiliary data, test conditions, and expected outcomes. An anomaly detected by a summary tool is a lead for investigation, not automatically proof of a processing defect.

The AI assistant can help a user formulate questions and explain tool results, but the deterministic Python functions should perform the actual calculations. Critical conclusions should remain traceable to the source data, metadata, tool logic, and applicable requirements.

## 13. Troubleshooting guide

### Python cannot import `quality`

Confirm that `quality.py` is beside `server.py` in the project root. Run the test command from that directory and use the Python interpreter associated with the intended virtual environment. If the terminal indicates multiple active environments, inspect the selected interpreter and pytest executable.

### The sample file cannot be found

Run the sample-generation step from the project root and confirm that `data/sample.nc` exists. Relative paths are interpreted from the current working directory unless the application explicitly resolves them relative to its own location.

### A variable or dataset is not found

Check the exact variable name in the NetCDF dataset or the exact dataset path in the HDF5 file. Names are case-sensitive, and an HDF5 dataset path may include groups.

### Statistics look unreasonable

Check whether the file has already been decoded by xarray. If the program reads raw packed values, it must apply scale and offset exactly once. If xarray has already applied masking or scaling, repeating the decoding step can produce incorrect results. Also inspect fill-value metadata, units, valid ranges, and the product specification.

### MCP server startup fails

Check the installed MCP SDK version and confirm that the server class, decorators, and run method used in `server.py` are supported by that version. Separate startup/API errors from errors in `quality.py` by running the unit tests independently.

### The tool runs out of memory

The current approach may load an entire dataset into memory. For large products, process a slice or chunk at a time and update running counts and statistics. Do not assume that a variable small enough for the synthetic example is representative of real satellite products.

## 14. Project structure

The intended project layout is:

- `server.py` — MCP server and tool definitions.
- `quality.py` — reusable data-quality calculations.
- `create_sample.py` — generates deterministic synthetic test data.
- `data/sample.nc` — generated NetCDF input.
- `tests/test_quality.py` — unit tests for the quality functions.
- `.venv/` — local Python virtual environment, which should not normally be committed to version control.

The README explains the design and workflow; implementation details remain in the Python modules and tests.

## 15. Summary

This project combines scientific-data handling with a simple MCP interface. It starts with a controlled synthetic dataset, implements reusable quality checks, verifies those checks using unit tests, and exposes the functions as tools an AI application can call.

The central design principle is to keep **deterministic data processing separate from natural-language interaction**. MCP provides the interface, while Python, NumPy, xarray, and HDF5/NetCDF libraries perform the actual inspection. That separation makes the project easier to test, debug, extend, and eventually adapt to more realistic satellite product-quality workflows.
# satellite-mcp
