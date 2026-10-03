from swe_agent.limits import Deadline, Incomplete, clip

class VerificationLoop:
    def __init__(
            self,
            swe_agent,
            judge_agent,
            sandbox,
            max_retries=5,
            approval_callback=None,
            deadline=None,
    ):
        self.deadline = deadline or Deadline(900)
        self.swe_agent = swe_agent
        self.judge_agent = judge_agent
        self.sandbox = sandbox
        self.max_retries = max_retries
        self.approval_callback = (
                approval_callback or self._default_approval
        )


    def run(self, issue_text):
        feedback = None
        history = []
        result = {"status": "needs_manual_review", "attempts": history,
                  "diff": None, "verdict": None}
        try:
            for attempt in range(1, self.max_retries + 1):
                self.deadline.remaining()
                record = {"attempt": attempt, "agent": {"status": "running"}}
                history.append(record)
                agent_result = self.swe_agent.run(issue_text, feedback=feedback)
                record["agent"] = agent_result
                diff, snapshot = self._capture_candidate()
                result.update(diff=diff, attempt=attempt)
                if agent_result.get("status") != "done":
                    result["status"] = "agent_incomplete"
                    break
                if not diff["git_diff"].strip():
                    result["status"] = "no_changes"
                    break
                verdict = self.judge_agent.evaluate(issue_text, diff)
                record["verdict"] = verdict
                result["verdict"] = verdict
                self._assert_candidate_unchanged(snapshot)
                if verdict.get("result") == "incomplete":
                    result["status"] = "judge_incomplete"
                    break

                failed_checks = verdict.get("failed_checks", [])
                if "verification_incomplete" in failed_checks:
                    # The patch may be correct; only the evidence is missing.
                    # Do not send this as code feedback to the SWE agent.
                    result["status"] = "judge_incomplete"
                    result["stop_reason"] = "verification_incomplete"
                    break
                if verdict.get("result") == "pass":
                    self.deadline.remaining()
                    with self.deadline.paused():
                        approved = self.approval_callback(diff, verdict)
                    if not approved:
                        result["status"] = "rejected_by_human"
                        break
                    self.deadline.remaining()
                    self._assert_candidate_unchanged(snapshot)
                    self._commit(snapshot)
                    result["status"] = "committed"
                    break
                feedback = clip(verdict.get("reasoning", ""), 8_000)
        except Incomplete as error:
            result.update(status=error.status, error=str(error))
            if history and history[-1]["agent"].get("status") == "running":
                history[-1]["agent"] = {"status": error.status, "error": str(error)}
        except Exception as error:
            result.update(status="error", error=clip(f"{type(error).__name__}: {error}"))
        finally:
            # Recovery has its own budget; an expired work deadline must not
            # prevent preservation of edits from the last, unfinished attempt.
            old_deadline = self.sandbox.deadline
            self.sandbox.deadline = Deadline(90)
            try:
                result["diff"] = self.sandbox.get_diff()
                result["patch_complete"] = True
            except Exception as error:
                result["diff"] = None
                result["patch_complete"] = False
                result["patch_error"] = clip(str(error))
            finally:
                self.sandbox.deadline = old_deadline
        return result

    def _capture_candidate(self):
        diff = self.sandbox.get_diff()

        head_result = self.sandbox.run_checked([
            "git", "rev-parse", "HEAD",
        ])

        if (self.sandbox.base_commit is not None
                and head_result["stdout"].strip() != self.sandbox.base_commit):
            raise Incomplete("base_commit_changed", "Agent changed Git history")

        tree_result = self.sandbox.run_checked([
            "git", "write-tree",
        ])

        snapshot = {
            "head": head_result["stdout"].strip(),
            "tree": tree_result["stdout"].strip(),
        }

        return diff, snapshot

    def _assert_candidate_unchanged(self, expected_snapshot):
        _, current_snapshot = self._capture_candidate()

        if current_snapshot != expected_snapshot:
            raise RuntimeError(
                "The proposed changes or base commit changed "
                "during review or approval. "
                "Stopped: the updated candidate needs a new review."
            )

    def _commit(self, expected_snapshot):
        self.sandbox.run_checked([
            "git",
            "-c", "user.email=agent@example.com",
            "-c", "user.name=SWE Agent",
            "-c", "core.hooksPath=/dev/null",
            "commit",
            "-m", "Automated fix",
        ])

        committed_tree = self.sandbox.run_checked([
            "git", "rev-parse", "HEAD^{tree}",
        ])

        if committed_tree["stdout"].strip() != expected_snapshot["tree"]:
            raise RuntimeError(
                "The commit was created, but its contents differ "
                "from the approved candidate. Manual review is required."
            )

    @staticmethod
    def _default_approval(diff, verdict):
        print("=" * 60)
        print("PROPOSED CHANGE")
        print("=" * 60)
        print(diff["git_diff"])

        print("=" * 60)
        print("JUDGE REASONING")
        print("=" * 60)
        print(verdict.get("reasoning", "(none provided)"))

        print("=" * 60)
        print("PROOF (commands the judge actually ran, and their output)")
        print("=" * 60)
        for message in verdict.get("messages", []):
            if message.get("role") == "tool":
                print(f"[{message.get('tool_name')}] ->")
                print(message.get("content"))
                print("-" * 40)

        answer = input("Approve and commit this change? [y/N] ")
        return answer.strip().lower() == "y"
