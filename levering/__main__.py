"""python3 -m levering <opdracht>: zie levering/__init__.py."""
import sys

sys.dont_write_bytecode = True

from .opdrachten import main  # noqa: E402

sys.exit(main())
