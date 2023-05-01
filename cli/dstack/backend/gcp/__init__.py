import warnings
from datetime import datetime
from typing import Generator, List, Optional

from google.auth._default import _CLOUD_SDK_CREDENTIALS_WARNING
from google.oauth2 import service_account

from dstack.backend.base import Backend
from dstack.backend.base import artifacts as base_artifacts
from dstack.backend.base import cache as base_cache
from dstack.backend.base import jobs as base_jobs
from dstack.backend.base import repos as base_repos
from dstack.backend.base import runs as base_runs
from dstack.backend.base import secrets as base_secrets
from dstack.backend.base import tags as base_tags
from dstack.backend.gcp.compute import GCPCompute
from dstack.backend.gcp.config import GCPConfig
from dstack.backend.gcp.logs import GCPLogging
from dstack.backend.gcp.secrets import GCPSecretsManager
from dstack.backend.gcp.storage import GCPStorage
from dstack.cli.common import console
from dstack.core.artifact import Artifact
from dstack.core.job import Job, JobHead, JobStatus
from dstack.core.log_event import LogEvent
from dstack.core.repo import RemoteRepoCredentials, RepoHead, RepoSpec
from dstack.core.run import RunHead
from dstack.core.secret import Secret
from dstack.core.tag import TagHead
from dstack.utils.common import PathLike

warnings.filterwarnings("ignore", message=_CLOUD_SDK_CREDENTIALS_WARNING)


class GCPBackend(Backend):
    NAME = "gcp"
    backend_config: GCPConfig
    _storage: GCPStorage
    _compute: GCPCompute
    _secrets_manager: GCPSecretsManager

    def __init__(
        self,
        backend_config: GCPConfig,
    ):
        super().__init__(backend_config=backend_config)
        credentials = service_account.Credentials.from_service_account_info(
            self.backend_config.credentials
        )
        self._storage = GCPStorage(
            project_id=self.backend_config.project_id,
            bucket_name=self.backend_config.bucket_name,
            credentials=credentials,
        )
        self._compute = GCPCompute(gcp_config=self.backend_config, credentials=credentials)
        self._secrets_manager = GCPSecretsManager(
            project_id=self.backend_config.project_id,
            bucket_name=self.backend_config.bucket_name,
            credentials=credentials,
        )
        self._logging = GCPLogging(
            project_id=self.backend_config.project_id,
            bucket_name=self.backend_config.bucket_name,
            credentials=credentials,
        )

    def create_run(self, repo_id: str) -> str:
        return base_runs.create_run(self._storage)

    def create_job(self, job: Job):
        if job.artifact_specs and any(art_spec.mount for art_spec in job.artifact_specs):
            console.print("Mount artifacts are not currently supported for 'gcp' backend")
            exit(1)
        base_jobs.create_job(self._storage, job)

    def get_job(self, repo_id: str, job_id: str) -> Optional[Job]:
        return base_jobs.get_job(self._storage, repo_id, job_id)

    def list_jobs(self, repo_id: str, run_name: str) -> List[Job]:
        return base_jobs.list_jobs(self._storage, repo_id, run_name)

    def run_job(self, job: Job, failed_to_start_job_new_status: JobStatus):
        base_jobs.run_job(self._storage, self._compute, job, failed_to_start_job_new_status)

    def stop_job(self, repo_id: str, abort: bool, job_id: str):
        base_jobs.stop_job(self._storage, self._compute, repo_id, job_id, abort)

    def list_job_heads(self, repo_id: str, run_name: Optional[str] = None) -> List[JobHead]:
        return base_jobs.list_job_heads(self._storage, repo_id, run_name)

    def delete_job_head(self, repo_id: str, job_id: str):
        base_jobs.delete_job_head(self._storage, repo_id, job_id)

    def list_run_heads(
        self,
        repo_id: str,
        run_name: Optional[str] = None,
        include_request_heads: bool = True,
        interrupted_job_new_status: JobStatus = JobStatus.FAILED,
    ) -> List[RunHead]:
        job_heads = self.list_job_heads(repo_id=repo_id, run_name=run_name)
        return base_runs.get_run_heads(
            self._storage,
            self._compute,
            job_heads,
            include_request_heads,
            interrupted_job_new_status,
        )

    def poll_logs(
        self,
        repo_id: str,
        run_name: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        descending: bool = False,
    ) -> Generator[LogEvent, None, None]:
        yield from self._logging.poll_logs(
            storage=self._storage,
            repo_id=repo_id,
            run_name=run_name,
            start_time=start_time,
            end_time=end_time,
            descending=descending,
        )

    def list_run_artifact_files(self, repo_id: str, run_name: str) -> List[Artifact]:
        return base_artifacts.list_run_artifact_files(self._storage, repo_id, run_name)

    def download_run_artifact_files(
        self,
        repo_id: str,
        run_name: str,
        output_dir: Optional[PathLike],
        files_path: Optional[PathLike] = None,
    ):
        artifacts = self.list_run_artifact_files(repo_id, run_name=run_name)
        base_artifacts.download_run_artifact_files(
            storage=self._storage,
            repo_id=repo_id,
            artifacts=artifacts,
            output_dir=output_dir,
            files_path=files_path,
        )

    def upload_job_artifact_files(
        self,
        repo_id: str,
        job_id: str,
        artifact_name: str,
        artifact_path: PathLike,
        local_path: PathLike,
    ):
        base_artifacts.upload_job_artifact_files(
            storage=self._storage,
            repo_id=repo_id,
            job_id=job_id,
            artifact_name=artifact_name,
            artifact_path=artifact_path,
            local_path=local_path,
        )

    def list_tag_heads(self, repo_id: str) -> List[TagHead]:
        return base_tags.list_tag_heads(self._storage, repo_id)

    def get_tag_head(self, repo_id: str, tag_name: str) -> Optional[TagHead]:
        return base_tags.get_tag_head(self._storage, repo_id, tag_name)

    def add_tag_from_run(
        self, repo_id: str, tag_name: str, run_name: str, run_jobs: Optional[List[Job]]
    ):
        base_tags.create_tag_from_run(
            self._storage,
            repo_id,
            tag_name,
            run_name,
            run_jobs,
        )

    def add_tag_from_local_dirs(self, tag_name: str, local_dirs: List[str]):
        # base_tags.create_tag_from_local_dirs(
        #     self._storage,
        #     self.repo,
        #     tag_name,
        #     local_dirs,
        # )
        raise NotImplementedError()

    def delete_tag_head(self, repo_id: str, tag_head: TagHead):
        base_tags.delete_tag(self._storage, repo_id, tag_head)

    def list_repo_heads(self) -> List[RepoHead]:
        return base_repos.list_repo_heads(self._storage)

    def update_repo_last_run_at(self, repo_spec: RepoSpec, last_run_at: int):
        base_repos.update_repo_last_run_at(
            self._storage,
            repo_spec,
            last_run_at,
        )

    def get_repo_credentials(self, repo_id: str) -> Optional[RemoteRepoCredentials]:
        return base_repos.get_repo_credentials(self._secrets_manager, repo_id)

    def save_repo_credentials(self, repo_id: str, repo_credentials: RemoteRepoCredentials):
        base_repos.save_repo_credentials(self._secrets_manager, repo_id, repo_credentials)

    def list_secret_names(self, repo_id: str) -> List[str]:
        return base_secrets.list_secret_names(self._storage, repo_id)

    def get_secret(self, repo_id: str, secret_name: str) -> Optional[Secret]:
        return base_secrets.get_secret(self._secrets_manager, repo_id, secret_name)

    def add_secret(self, repo_id: str, secret: Secret):
        base_secrets.add_secret(self._storage, self._secrets_manager, repo_id, secret)

    def update_secret(self, repo_id: str, secret: Secret):
        base_secrets.update_secret(self._storage, self._secrets_manager, repo_id, secret)

    def delete_secret(self, repo_id: str, secret_name: str):
        base_secrets.delete_secret(self._storage, self._secrets_manager, repo_id, secret_name)

    def get_signed_download_url(self, object_key: str) -> str:
        return self._storage.get_signed_download_url(object_key)

    def get_signed_upload_url(self, object_key: str) -> str:
        return self._storage.get_signed_upload_url(object_key)

    def delete_workflow_cache(self, repo_id: str, hub_user_name: str, workflow_name: str):
        base_cache.delete_workflow_cache(self._storage, repo_id, hub_user_name, workflow_name)
