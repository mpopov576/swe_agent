from contextlib import contextmanager

from swe_agent.verification_loop import VerificationLoop


class FakeDeadline:
    def remaining(self):
        return 999

    @contextmanager
    def paused(self):
        yield


class FakeSWEAgent:
    def __init__(self):
        self.calls = []

    def run(self, issue_text, feedback=None):
        self.calls.append({
            "issue_text": issue_text,
            "feedback": feedback,
        })

        return {
            "status": "done",
        }


class FakeJudgeAgent:
    def __init__(self, verdicts):
        self.verdicts = list(verdicts)
        self.calls = []
        self.index = 0

    def evaluate(self, issue_text, diff):
        self.calls.append({
            "issue_text": issue_text,
            "diff": diff,
        })

        verdict = self.verdicts[self.index]
        self.index += 1

        return verdict


class FakeSandbox:
    def __init__(self, diffs=None):
        self.diffs = list(diffs or [])
        self.deadline = FakeDeadline()
        self.cleanup_failed = False
        self.commands = []

    def get_diff(self):
        if not self.diffs:
            return {
                "changed_files": "",
                "git_diff": "",
            }

        return self.diffs[-1]

    def run_command_in_sandbox(
        self,
        command,
        *,
        read_only=False,
        output_limit=32_768,
    ):
        self.commands.append(list(command))

        return {
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "stdout_truncated": False,
            "stderr_truncated": False,
            "capture_error": None,
        }


def make_loop(
    *,
    diffs,
    verdicts,
    max_retries=3,
    approval_callback=None,
):
    swe_agent = FakeSWEAgent()
    judge_agent = FakeJudgeAgent(verdicts)
    sandbox = FakeSandbox(diffs)

    if approval_callback is None:
        approval_callback = lambda diff, verdict: True

    loop = VerificationLoop(
        swe_agent=swe_agent,
        judge_agent=judge_agent,
        sandbox=sandbox,
        max_retries=max_retries,
        approval_callback=approval_callback,
    )

    remaining_diffs = iter(diffs)
    commits = []

    def capture_candidate():
        diff = next(remaining_diffs)

        # The production loop only needs an opaque snapshot token here.
        snapshot = diff["git_diff"]

        return diff, snapshot

    def assert_candidate_unchanged(snapshot):
        return None

    def commit(snapshot):
        commits.append(snapshot)

    # These tests exercise VerificationLoop orchestration.
    # Sandbox/git mechanics are covered separately by SandboxRunner tests.
    loop._capture_candidate = capture_candidate
    loop._assert_candidate_unchanged = assert_candidate_unchanged
    loop._commit = commit

    return loop, swe_agent, judge_agent, sandbox, commits


def test_verification_loop_commits_when_judge_passes_and_human_approves():
    diff = {
        "git_diff": "diff --git a/test.py b/test.py",
    }

    approval_calls = []

    def approve(candidate_diff, verdict):
        approval_calls.append(
            (candidate_diff, verdict)
        )
        return True

    loop, swe_agent, judge_agent, _, commits = make_loop(
        diffs=[diff],
        verdicts=[
            {
                "result": "pass",
                "reasoning": "The fix is correct.",
            }
        ],
        approval_callback=approve,
    )

    result = loop.run("Fix the bug")

    assert result["status"] == "committed"
    assert result["attempt"] == 1
    assert result["diff"] == diff
    assert result["verdict"]["result"] == "pass"

    assert len(result["attempts"]) == 1

    assert len(swe_agent.calls) == 1
    assert swe_agent.calls[0] == {
        "issue_text": "Fix the bug",
        "feedback": None,
    }

    assert len(judge_agent.calls) == 1
    assert len(approval_calls) == 1

    assert commits == [
        diff["git_diff"],
    ]


def test_verification_loop_returns_rejected_when_human_rejects():
    diff = {
        "git_diff": "some diff",
    }

    loop, _, _, _, commits = make_loop(
        diffs=[diff],
        verdicts=[
            {
                "result": "pass",
                "reasoning": "The fix looks correct.",
            }
        ],
        approval_callback=lambda diff, verdict: False,
    )

    result = loop.run("Fix the bug")

    assert result["status"] == "rejected_by_human"
    assert result["attempt"] == 1
    assert result["diff"] == diff
    assert result["verdict"]["result"] == "pass"

    assert len(result["attempts"]) == 1
    assert commits == []


def test_verification_loop_retries_after_judge_failure():
    diffs = [
        {
            "git_diff": "first diff",
        },
        {
            "git_diff": "second diff",
        },
    ]

    loop, swe_agent, judge_agent, _, commits = make_loop(
        diffs=diffs,
        verdicts=[
            {
                "result": "fail",
                "reasoning": "The tests still fail.",
            },
            {
                "result": "pass",
                "reasoning": "The second fix passes.",
            },
        ],
        max_retries=2,
    )

    result = loop.run("Fix the bug")

    assert result["status"] == "committed"
    assert result["attempt"] == 2
    assert len(result["attempts"]) == 2

    assert len(swe_agent.calls) == 2

    assert swe_agent.calls[0]["feedback"] is None
    assert (
        swe_agent.calls[1]["feedback"]
        == "The tests still fail."
    )

    assert len(judge_agent.calls) == 2

    assert commits == [
        "second diff",
    ]


def test_verification_loop_returns_manual_review_after_max_retries():
    diffs = [
        {
            "git_diff": "first diff",
        },
        {
            "git_diff": "second diff",
        },
        {
            "git_diff": "third diff",
        },
    ]

    loop, swe_agent, judge_agent, _, commits = make_loop(
        diffs=diffs,
        verdicts=[
            {
                "result": "fail",
                "reasoning": "First attempt failed.",
            },
            {
                "result": "fail",
                "reasoning": "Second attempt failed.",
            },
            {
                "result": "fail",
                "reasoning": "Third attempt failed.",
            },
        ],
        max_retries=3,
    )

    result = loop.run("Fix the bug")

    assert result["status"] == "needs_manual_review"
    assert len(result["attempts"]) == 3
    assert result["attempt"] == 3
    assert result["diff"] == diffs[-1]

    assert (
        result["verdict"]["reasoning"]
        == "Third attempt failed."
    )

    assert len(swe_agent.calls) == 3
    assert len(judge_agent.calls) == 3

    assert commits == []


def test_verification_loop_does_not_exceed_max_retries():
    diffs = [
        {
            "git_diff": "first diff",
        },
        {
            "git_diff": "second diff",
        },
    ]

    loop, swe_agent, judge_agent, _, commits = make_loop(
        diffs=diffs,
        verdicts=[
            {
                "result": "fail",
                "reasoning": "Failed.",
            },
            {
                "result": "fail",
                "reasoning": "Failed again.",
            },
        ],
        max_retries=2,
    )

    result = loop.run("Fix the bug")

    assert result["status"] == "needs_manual_review"
    assert len(result["attempts"]) == 2
    assert result["attempt"] == 2

    assert len(swe_agent.calls) == 2
    assert len(judge_agent.calls) == 2

    assert commits == []