from swe_agent.verification_loop import VerificationLoop


class FakeSWEAgent:
    def __init__(self):
        self.calls = []

    def run(self, issue_text, feedback=None):
        self.calls.append({
            "issue_text": issue_text,
            "feedback": feedback,
        })


class FakeJudgeAgent:
    def __init__(self, verdicts):
        self.verdicts = verdicts
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
        self.diffs = diffs or []
        self.diff_index = 0
        self.commands = []

    def get_diff(self):
        diff = self.diffs[self.diff_index]
        self.diff_index += 1
        return diff

    def run_command_in_sandbox(self, command):
        self.commands.append(command)

        return {
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
        }


def test_verification_loop_commits_when_judge_passes_and_human_approves():
    swe_agent = FakeSWEAgent()

    judge_agent = FakeJudgeAgent([
        {
            "result": "pass",
            "reasoning": "The fix is correct.",
        }
    ])

    diff = {
        "git_diff": "diff --git a/test.py b/test.py"
    }

    sandbox = FakeSandbox([diff])

    approval_calls = []

    def approve(diff, verdict):
        approval_calls.append((diff, verdict))
        return True

    loop = VerificationLoop(
        swe_agent=swe_agent,
        judge_agent=judge_agent,
        sandbox=sandbox,
        approval_callback=approve,
    )

    result = loop.run("Fix the bug")

    assert result["status"] == "committed"
    assert result["attempt"] == 1
    assert result["diff"] == diff
    assert result["verdict"]["result"] == "pass"

    assert len(swe_agent.calls) == 1
    assert swe_agent.calls[0]["issue_text"] == "Fix the bug"
    assert swe_agent.calls[0]["feedback"] is None

    assert len(judge_agent.calls) == 1
    assert len(approval_calls) == 1

    assert sandbox.commands == [
        ["git", "add", "-A"],
        [
            "git",
            "-c",
            "user.email=agent@example.com",
            "-c",
            "user.name=SWE Agent",
            "commit",
            "-m",
            "Automated fix",
        ],
    ]


def test_verification_loop_returns_rejected_when_human_rejects():
    swe_agent = FakeSWEAgent()

    judge_agent = FakeJudgeAgent([
        {
            "result": "pass",
            "reasoning": "The fix looks correct.",
        }
    ])

    diff = {
        "git_diff": "some diff"
    }

    sandbox = FakeSandbox([diff])

    loop = VerificationLoop(
        swe_agent=swe_agent,
        judge_agent=judge_agent,
        sandbox=sandbox,
        approval_callback=lambda diff, verdict: False,
    )

    result = loop.run("Fix the bug")

    assert result["status"] == "rejected_by_human"
    assert result["attempt"] == 1
    assert result["diff"] == diff
    assert result["verdict"]["result"] == "pass"

    assert sandbox.commands == []


def test_verification_loop_retries_after_judge_failure():
    swe_agent = FakeSWEAgent()

    judge_agent = FakeJudgeAgent([
        {
            "result": "fail",
            "reasoning": "The tests still fail.",
        },
        {
            "result": "pass",
            "reasoning": "The second fix passes.",
        },
    ])

    diffs = [
        {"git_diff": "first diff"},
        {"git_diff": "second diff"},
    ]

    sandbox = FakeSandbox(diffs)

    loop = VerificationLoop(
        swe_agent=swe_agent,
        judge_agent=judge_agent,
        sandbox=sandbox,
        max_retries=2,
        approval_callback=lambda diff, verdict: True,
    )

    result = loop.run("Fix the bug")

    assert result["status"] == "committed"
    assert result["attempt"] == 2

    assert len(swe_agent.calls) == 2

    assert swe_agent.calls[0]["feedback"] is None
    assert swe_agent.calls[1]["feedback"] == "The tests still fail."

    assert len(judge_agent.calls) == 2

    assert sandbox.commands == [
        ["git", "add", "-A"],
        [
            "git",
            "-c",
            "user.email=agent@example.com",
            "-c",
            "user.name=SWE Agent",
            "commit",
            "-m",
            "Automated fix",
        ],
    ]


def test_verification_loop_returns_manual_review_after_max_retries():
    swe_agent = FakeSWEAgent()

    judge_agent = FakeJudgeAgent([
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
    ])

    diffs = [
        {"git_diff": "first diff"},
        {"git_diff": "second diff"},
        {"git_diff": "third diff"},
    ]

    sandbox = FakeSandbox(diffs)

    loop = VerificationLoop(
        swe_agent=swe_agent,
        judge_agent=judge_agent,
        sandbox=sandbox,
        max_retries=3,
        approval_callback=lambda diff, verdict: True,
    )

    result = loop.run("Fix the bug")

    assert result["status"] == "needs_manual_review"
    assert result["attempts"] == 3
    assert result["diff"] == diffs[-1]
    assert result["verdict"]["reasoning"] == "Third attempt failed."

    assert len(swe_agent.calls) == 3
    assert len(judge_agent.calls) == 3

    assert sandbox.commands == []


def test_verification_loop_does_not_exceed_max_retries():
    swe_agent = FakeSWEAgent()

    judge_agent = FakeJudgeAgent([
        {
            "result": "fail",
            "reasoning": "Failed.",
        }
    ] * 5)

    sandbox = FakeSandbox([
        {"git_diff": "diff"}
    ] * 5)

    loop = VerificationLoop(
        swe_agent=swe_agent,
        judge_agent=judge_agent,
        sandbox=sandbox,
        max_retries=2,
        approval_callback=lambda diff, verdict: True,
    )

    result = loop.run("Fix the bug")

    assert result["status"] == "needs_manual_review"
    assert result["attempts"] == 2

    assert len(swe_agent.calls) == 2
    assert len(judge_agent.calls) == 2