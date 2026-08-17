import os
import time

from app.services.analytics.storage import cleanup_stale_temp_uploads


def _make_temp_file(base, user_id, filename, age_hours=0):
    user_dir = os.path.join(base, "tmp", str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    path = os.path.join(user_dir, filename)
    with open(path, "w") as f:
        f.write("test content")

    if age_hours:
        old_time = time.time() - (age_hours * 3600)
        os.utime(path, (old_time, old_time))

    return path


def test_cleanup_removes_files_older_than_max_age(tmp_path):
    upload_folder = str(tmp_path)
    old_file = _make_temp_file(upload_folder, user_id=1, filename="old.csv", age_hours=48)
    fresh_file = _make_temp_file(upload_folder, user_id=1, filename="fresh.csv", age_hours=0)

    deleted = cleanup_stale_temp_uploads(upload_folder, "tmp", max_age_hours=24)

    assert deleted == 1
    assert not os.path.isfile(old_file)
    assert os.path.isfile(fresh_file)


def test_cleanup_handles_multiple_users(tmp_path):
    upload_folder = str(tmp_path)
    old_1 = _make_temp_file(upload_folder, user_id=1, filename="a.csv", age_hours=48)
    old_2 = _make_temp_file(upload_folder, user_id=2, filename="b.csv", age_hours=48)
    fresh = _make_temp_file(upload_folder, user_id=2, filename="c.csv", age_hours=0)

    deleted = cleanup_stale_temp_uploads(upload_folder, "tmp", max_age_hours=24)

    assert deleted == 2
    assert not os.path.isfile(old_1)
    assert not os.path.isfile(old_2)
    assert os.path.isfile(fresh)


def test_cleanup_returns_zero_when_temp_folder_missing(tmp_path):
    upload_folder = str(tmp_path)
    deleted = cleanup_stale_temp_uploads(upload_folder, "tmp", max_age_hours=24)
    assert deleted == 0


def test_cleanup_returns_zero_when_nothing_is_stale(tmp_path):
    upload_folder = str(tmp_path)
    _make_temp_file(upload_folder, user_id=1, filename="fresh.csv", age_hours=1)

    deleted = cleanup_stale_temp_uploads(upload_folder, "tmp", max_age_hours=24)
    assert deleted == 0


def test_cleanup_is_safe_to_run_repeatedly(tmp_path):
    upload_folder = str(tmp_path)
    _make_temp_file(upload_folder, user_id=1, filename="old.csv", age_hours=48)

    first_run = cleanup_stale_temp_uploads(upload_folder, "tmp", max_age_hours=24)
    second_run = cleanup_stale_temp_uploads(upload_folder, "tmp", max_age_hours=24)

    assert first_run == 1
    assert second_run == 0


def test_cli_command_runs_successfully(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["cleanup-temp-uploads"])
    assert result.exit_code == 0
    assert "Deleted" in result.output
