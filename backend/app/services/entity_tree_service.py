"""Entity tree (hierarchical) and effective ownership calculation."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company_entity import CompanyEntity, OwnershipLink


class EntityTreeService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_tree(self, org_id: int) -> list[dict]:
        """Build entity tree for organization."""
        q = select(CompanyEntity).where(
            CompanyEntity.organization_id == org_id
        ).order_by(CompanyEntity.id)
        result = await self.session.execute(q)
        entities = list(result.scalars().all())

        # Get ownership links
        entity_ids = [e.id for e in entities]
        if not entity_ids:
            return []

        links_q = select(OwnershipLink).where(
            OwnershipLink.parent_entity_id.in_(entity_ids)
        )
        links_result = await self.session.execute(links_q)
        links = list(links_result.scalars().all())

        # Build lookup
        ownership_map: dict[int, list[dict]] = {}
        for link in links:
            ownership_map.setdefault(link.child_entity_id, []).append({
                "parent_id": link.parent_entity_id,
                "percent": float(link.ownership_percent),
                "type": link.ownership_type,
            })

        # Build tree
        by_id: dict[int, dict] = {}
        for e in entities:
            by_id[e.id] = {
                "id": e.id,
                "name": e.name,
                "code": e.code,
                "entity_type": e.entity_type,
                "country": e.country,
                "status": e.status,
                "parent_entity_id": e.parent_entity_id,
                "ownership": ownership_map.get(e.id, []),
                "children": [],
            }

        roots: list[dict] = []
        for e in entities:
            node = by_id[e.id]
            if e.parent_entity_id and e.parent_entity_id in by_id:
                by_id[e.parent_entity_id]["children"].append(node)
            else:
                roots.append(node)

        return roots

    async def calculate_effective_ownership(self, org_id: int, target_entity_id: int) -> dict:
        """Calculate effective ownership through the chain using DFS."""
        q = select(OwnershipLink).join(
            CompanyEntity, CompanyEntity.id == OwnershipLink.parent_entity_id
        ).where(CompanyEntity.organization_id == org_id)
        result = await self.session.execute(q)
        links = list(result.scalars().all())

        # Build graph: parent_id → [(child_id, percent)]
        children_map: dict[int, list[tuple[int, float]]] = {}
        for link in links:
            children_map.setdefault(link.parent_entity_id, []).append(
                (link.child_entity_id, float(link.ownership_percent))
            )

        # Find root entities (no parent ownership)
        all_children = {link.child_entity_id for link in links}
        all_parents = {link.parent_entity_id for link in links}
        roots = all_parents - all_children

        # DFS from each root
        effective: dict[int, float] = {}

        def dfs(entity_id: int, accumulated: float, visited: set):
            if entity_id in visited:
                return  # Cycle detected
            visited.add(entity_id)

            if entity_id == target_entity_id:
                effective[entity_id] = effective.get(entity_id, 0) + accumulated

            for child_id, percent in children_map.get(entity_id, []):
                dfs(child_id, accumulated * percent / 100, visited.copy())

        for root in roots:
            dfs(root, 100.0, set())

        return {
            "entity_id": target_entity_id,
            "effective_ownership_percent": round(effective.get(target_entity_id, 0), 4),
        }
