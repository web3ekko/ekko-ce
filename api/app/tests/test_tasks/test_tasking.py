from django.test import SimpleTestCase, override_settings

from app.tasks.tasking import TaskWrapper, task


class TestTasking(SimpleTestCase):
    def test_task_uses_thread_wrapper_with_immediate_backend(self) -> None:
        with override_settings(
            TASKS={
                "default": {
                    "BACKEND": "django.tasks.backends.immediate.ImmediateBackend",
                    "QUEUES": ["default", "nlp"],
                }
            }
        ):
            @task(queue_name="nlp")
            def sample_task() -> None:
                return None

            self.assertIsInstance(sample_task, TaskWrapper)
