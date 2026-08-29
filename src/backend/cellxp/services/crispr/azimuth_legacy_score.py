# mypy: ignore-errors
"""JSON subprocess bridge for the pinned Python-2 Azimuth v2.0 environment."""


import json
import sys

from cStringIO import StringIO

REVISION = "73522accfde9d609563231efcc5f3b284af78566"


def main():
    if "--version" in sys.argv:
        print("azimuth-rule-set-2 " + REVISION)
        return 0
    import azimuth.model_comparison
    import numpy

    payload = json.load(sys.stdin)
    guides = payload["guides"]
    contexts = numpy.asarray(payload["contexts"])
    if len(contexts) != len(guides) or any(len(context) != 30 for context in contexts):
        raise ValueError("one real 30-bp genomic context is required per guide")
    original_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        scores = azimuth.model_comparison.predict(contexts, None, None)
    finally:
        sys.stdout = original_stdout
    print(json.dumps({"scores": dict(zip(guides, [float(value) for value in scores]))}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
