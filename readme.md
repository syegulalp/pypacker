# PyPacker: a dumb little script for turning Python apps into standalone executable packages on Windows

PyPacker is my attempt at creating a way to make Python apps fully portable on Windows. It does this by performing *live program analysis* to determine what to pack up.

## Rationale

Most systems for turning Python apps into standalone programs analyze the program to determine what and how to pack things up, but don't actually run the program in question, and so have no information about the program's runtime behavior.

PyPacker runs the program and makes a record of all the imports actually used during the program's lifetime. It then uses this information to create a standalone redistributable of the application.

The downside of this approach is that you have to perform at least one run with the program that provides the broadest possible program coverage -- e.g., all imports are fully executed, etc.

The upside is that PyPacker knows exactly what to copy. Also, your trace files can be reused as long as no new program components have been added in the meantime.

## Usage

Run it like so:

`py -m pypacker -a entry_point.py`

where `entry_point.py` is the entry point to your application.

Your application will launch. Run it and make sure you use as much of its functionality as possible, to generate the maximum possible coverage.

When your application exits, PyPacker it will generate a `tracefile.json` file that can be re-used for future runs (by just typing `py -m pypacker` in that directory). It will then package your application for redistribution.

The resulting redistributable will be placed in the `dist` subdirectory. A zipped version of the redistributable directory is also provided.

## What PyPacker tries to do

* The main program tree is turned into a `.zip` file (of `.pyc` files).
* Any non-Python files in the main program tree are copied into a parallel directory off the root of the `dist` directory.
* Usage of `.pyd` files and (some) `.dll`s are automatically detected as well and copied.
* Third-party packages are also included.
* Both console and windowed executables are provided.

Note that PyPacker works best with a program structure like this:

```
entrypoint.py
    \ appdir
```

where `entrypoint.py` is what's executed to start your app, and your actual app and all its files live in `appdir` and below. This makes it easier for PyPacker to detect data files that are adjacent to your application.

## Options

The following command line options are supported:

* `-a` -- Specify an entry point for analysis. Not needed if you're re-using a previously generated analysis.
* `-v` -- Verbose output.
* `-ta` -- Treeshaking analysis on the application. Attempts to copy *only* the application modules that ran during the analysis phase.
* `-tl` -- Treeshaking analysis on the libraries. Attempts to copy *only* the library modules that ran during the analysis phase.
* `-t` -- Shortcut for `-ta` and `-tl`.

## Caveats

Very buggy. Drastically incomplete. For instance, stuff like NumPy probably doesn't work yet.

Treeshaking is highly experimental.

If you are packing up a single file that requires the presence of other non-Python files, they will not be detected. I'm working on a mechanism to allow arbitrary files to be added to the package.

## License

MIT