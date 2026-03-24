from httpx import AsyncClient

from app.collectors.android import AndroidBulletinIndexAdapter, GitilesLogAdapter
from app.collectors.base import SourceAdapter
from app.collectors.kernel_org import KernelOrgReleasesAdapter
from app.collectors.lore import LoreListAdapter


class CollectorRegistry:
    def __init__(self, http_client: AsyncClient) -> None:
        self._adapters: dict[str, SourceAdapter] = {
            "android_bulletin_index": AndroidBulletinIndexAdapter(http_client),
            "gitiles_log": GitilesLogAdapter(http_client),
            "kernel_org_releases": KernelOrgReleasesAdapter(http_client),
            "lore_list": LoreListAdapter(http_client),
        }

    def get(self, adapter_name: str) -> SourceAdapter:
        try:
            return self._adapters[adapter_name]
        except KeyError as exc:
            raise KeyError(f"Unknown adapter: {adapter_name}") from exc
