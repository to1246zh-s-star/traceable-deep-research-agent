"""Evaluate a persisted research run with deterministic Agent metrics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(
    __file__
).resolve().parents[1]

SRC_ROOT = (
    BACKEND_ROOT
    / "src"
)

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_ROOT),
    )


from services.agent_eval_dataset import (  # noqa: E402
    load_eval_cases,
)
from services.agent_eval_runner import (  # noqa: E402
    evaluate_research_state,
    serialize_research_eval,
)
from services.agent_eval_regression import (  # noqa: E402
    REGRESSION,
    compare_eval_payloads,
    serialize_regression_result,
)
from services.research_store import (  # noqa: E402
    SQLiteResearchStore,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate one persisted research run."
        )
    )

    parser.add_argument(
        "--research-id",
        required=True,
        help="Persisted research ID.",
    )

    parser.add_argument(
        "--db-path",
        required=True,
        help="SQLite research database path.",
    )

    parser.add_argument(
        "--cases",
        default=str(
            BACKEND_ROOT
            / "eval"
            / "cases.json"
        ),
        help="Evaluation case dataset.",
    )

    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Optional JSON output path."
        ),
    )

    parser.add_argument(
        "--baseline",
        default=None,
        help=(
            "Optional previous evaluation JSON used "
            "for deterministic regression comparison."
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    store = SQLiteResearchStore(
        args.db_path
    )

    state = store.get(
        args.research_id
    )

    if state is None:
        print(
            json.dumps(
                {
                    "error":
                        "research_not_found",
                    "research_id":
                        args.research_id,
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )

        return 2

    cases = load_eval_cases(
        args.cases
    )

    result = evaluate_research_state(
        research_id=(
            args.research_id
        ),
        state=state,
        cases=cases,
    )

    payload = (
        serialize_research_eval(
            result
        )
    )

    regression_detected = False

    if args.baseline:
        baseline_path = Path(
            args.baseline
        )

        baseline_payload = json.loads(
            baseline_path.read_text(
                encoding="utf-8"
            )
        )

        regression = compare_eval_payloads(
            baseline_payload=baseline_payload,
            current_payload=payload,
        )

        payload["regression"] = (
            serialize_regression_result(
                regression
            )
        )

        regression_detected = (
            regression.status
            == REGRESSION
        )

    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )

    if args.output:
        output_path = Path(
            args.output
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path.write_text(
            rendered + "\n",
            encoding="utf-8",
        )

    print(
        rendered
    )

    return (
        3
        if regression_detected
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
