"""World packages (dungeon/packages.py): /api/packages."""
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pydantic import Field

from dungeon import package_import, packages
from dungeon.errors import require
from dungeon.models import Input

router = APIRouter(prefix='/api/packages')


def root(request: Request) -> Path:
    return request.app.state.database.root


def found(request: Request, world_id: str) -> Path:
    if world_id in packages.builtin_ids():
        return packages.installed(root(request), world_id)
    path = root(request) / packages.FOLDER / f'{world_id}.sqlite'
    require(packages.ID.match(world_id) is not None and path.is_file(), 'That world package does not exist.', 404)
    return path


@router.get('')
def listing(request: Request):
    """The built-in worlds and the ones imported, each with what it holds."""
    folder = root(request) / packages.FOLDER
    imported = sorted(path.stem for path in folder.glob('*.sqlite')) if folder.is_dir() else []
    ids = packages.builtin_ids() + [world_id for world_id in imported if world_id not in packages.builtin_ids()]
    return {'packages': [packages.summary(found(request, world_id)) | {'builtin': world_id in packages.builtin_ids()}
                         for world_id in ids]}


@router.get('/{world_id}/file')
def download(request: Request, world_id: str):
    """The world as its one SQLite file, to share."""
    return FileResponse(found(request, world_id), filename=f'{world_id}.sqlite', media_type='application/vnd.sqlite3')


@router.post('/{world_id}/export')
def export(request: Request, world_id: str):
    """The world written out as a folder of Markdown and JSON in the data folder (exports/), for bulk edits."""
    stamp = datetime.now().strftime('%Y-%m-%d-%H%M%S')
    folder = packages.export(found(request, world_id), root(request) / 'exports' / f'{world_id}-{stamp}')
    return {'folder': str(folder)}


class FolderImport(Input):
    folder: str = Field(min_length=1, max_length=1000)


@router.post('/import')
def import_folder(request: Request, body: FolderImport):
    """A world folder on this computer, checked and made into a package."""
    return packages.import_folder(root(request), Path(body.folder).expanduser())


class ImportFile(Input):
    name: str = Field(min_length=1, max_length=300)
    text: str = Field(max_length=package_import.MAX_BYTES)


class DraftStart(Input):
    name: str = Field(min_length=1, max_length=120)
    files: list[ImportFile] = Field(min_length=1, max_length=package_import.MAX_FILES)


class SectionReview(Input):
    status: str = Field(pattern='^(empty|drafted|approved)$')
    entries: list[dict] | None = Field(default=None, max_length=5000)


class DraftFinish(Input):
    replace: bool = False


@router.get('/drafts')
def drafts(request: Request):
    """The world imports still being reviewed."""
    return {'drafts': package_import.drafts(root(request))}


@router.post('/drafts')
def start_draft(request: Request, body: DraftStart):
    """A world import from the world's files: documents kept, a lorebook read as the lore section."""
    return package_import.start(root(request), body.name, [item.model_dump() for item in body.files],
                                request.app.state.database.now())


@router.get('/drafts/{draft_id}')
def draft(request: Request, draft_id: str):
    return package_import.view(package_import.load(root(request), draft_id))


@router.post('/drafts/{draft_id}/sections/{section}/draft')
async def draft_section(request: Request, draft_id: str, section: str):
    """One section drafted by the World importer's model from the documents."""
    return await package_import.draft_section(request.app.state, root(request), draft_id, section)


@router.put('/drafts/{draft_id}/sections/{section}')
def review_section(request: Request, draft_id: str, section: str, body: SectionReview):
    """The author's edits to a section, and whether it is approved."""
    return package_import.review(root(request), draft_id, section, body.entries, body.status)


@router.post('/drafts/{draft_id}/finish')
def finish_draft(request: Request, draft_id: str, body: DraftFinish):
    """The approved sections written as the world's package."""
    return package_import.finish(root(request), draft_id, body.replace)


@router.delete('/drafts/{draft_id}')
def remove_draft(request: Request, draft_id: str):
    package_import.remove(root(request), draft_id)
    return {'ok': True}
