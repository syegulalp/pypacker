# PyPacker: a dumb little script for turning Python apps into standalone executable packages

PyPacker is my attempt at creating a way to make Python apps fully portable on Windows. It does this by performing live program analysis to determine what to pack up.

## Rationale

Most systems for turning Python apps into standalone programs analyze the program to determine what and how to pack things up, but don't actually run the program in question. PyPacker runs the program and makes a record of all the imports actually used during the program's lifetime.

The downside of this approach is that you have to perform at least one run with the program that provides the broadest possible program coverage -- e.g., all imports are fully executed, etc. The upside is that PyPacker knows what to copy. Also, your trace files can be reused as long as no new program components have been added in the meantime.

## Usage

Run it like so:

`py -m pypacker -a entry_point.py`

where `entry_point.py` is the entry point to your application.

The application will launch. Run it and make sure you use as much of its functionality as possible.

When finished, it will generate `tracefile.json` that can be re-used for future runs (by just typing `py -m pypacker` in that directory).

The resulting redistributable will be placed in the `dist` subdirectory.

## Caveats

Very buggy. Drastically incomplete.

## License

MIT