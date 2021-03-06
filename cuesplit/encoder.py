import asyncio
import glob
import os
import re

from . import version


async def set_track_name(metadata, num, ext):
    e = r'[\\/|?<>*:]'
    return '{0} - {1} - {2}{3}'.format(
        metadata['tracks'][num]['num'],
        re.sub(e, '~', metadata['tracks'][num]['performer']),
        re.sub(e, '~', metadata['tracks'][num]['title']),
        ext)


async def get_flac(metadata, num, filename, opts):
    new = await set_track_name(metadata, num, '.flac')
    pic = None
    if 'cover front' in metadata:
        pic = f' --picture=\"3||front cover||{metadata["cover front"]}\"'
    t = f'{int(metadata["tracks"][num]["num"])}/{len(metadata["tracks"])}'
    cmd = 'flac {0} -f -o "{1}"{2}{3}{4}{5}{6}{7}{8}{9} {10}'.format(
        opts or '-8',
        new,
        f' --tag=artist=\"{metadata["tracks"][num]["performer"]}\"',
        f' --tag=album=\"{metadata["album"]}\"',
        f' --tag=genre=\"{metadata["genre"]}\"',
        f' --tag=title=\"{metadata["tracks"][num]["title"]}\"',
        f' --tag=tracknumber=\"{t}\"',
        f' --tag=date=\"{metadata["date"]}\"',
        f' --tag=comment=\"{metadata["commentary"] or version}\"',
        pic or '',
        filename)
    return new, cmd


async def get_mp3(metadata, num, filename, opts):
    new = await set_track_name(metadata, num, '.mp3')
    pic = None
    if 'cover front' in metadata:
        pic = f' --ti \"{metadata["cover front"]}\"'
    t = f'{int(metadata["tracks"][num]["num"])}/{len(metadata["tracks"])}'
    cmd = 'lame{0}{1}{2}{3}{4}{5}{6}{7}{8}{9} {10} \"{11}\"'.format(
        f'{opts or " -b 320"} --lowpass -1 --noreplaygain',
        ' --id3v2-only --id3v2-utf16',
        f' --ta \"{metadata["tracks"][num]["performer"]}\"',
        f' --tl \"{metadata["album"]}\"',
        f' --tg \"{metadata["genre"]}\"',
        f' --tt \"{metadata["tracks"][num]["title"]}\"',
        f' --tn \"{t}\"',
        f' --ty \"{metadata["date"]}\"',
        f' --tv \"COMM=={metadata["commentary"] or version}\"',
        pic or '',
        filename,
        new)
    return new, cmd


async def get_opus(metadata, num, filename, opts):
    new = await set_track_name(metadata, num, '.opus')
    pic = None
    if 'cover front' in metadata:
        pic = f' --picture \"3||front cover||{metadata["cover front"]}\"'
    t = f'{int(metadata["tracks"][num]["num"])}/{len(metadata["tracks"])}'
    cmd = 'opusenc{0}{1}{2}{3}{4}{5}{6}{7}{8} {9} \"{10}\"'.format(
        opts or '',
        f' --artist \"{metadata["tracks"][num]["performer"]}\"',
        f' --album \"{metadata["album"]}\"',
        f' --genre \"{metadata["genre"]}\"',
        f' --title \"{metadata["tracks"][num]["title"]}\"',
        f' --comment tracknumber=\"{t}\"',
        f' --date \"{metadata["date"]}\"',
        f' --comment comment=\"{metadata["commentary"] or version}\"',
        pic or '',
        filename,
        new)
    return new, cmd


async def get_vorbis(metadata, num, filename, opts):
    new = await set_track_name(metadata, num, '.ogg')
    t = f'{int(metadata["tracks"][num]["num"])}/{len(metadata["tracks"])}'
    cmd = 'oggenc {0}{1}{2}{3}{4}{5}{6}{7} -o \"{8}\" {9}'.format(
        opts or '-q 4',
        f' --artist \"{metadata["tracks"][num]["performer"]}\"',
        f' --album \"{metadata["album"]}\"',
        f' --genre \"{metadata["genre"]}\"',
        f' --title \"{metadata["tracks"][num]["title"]}\"',
        f' --comment tracknumber=\"{t}\"',
        f' --date \"{metadata["date"]}\"',
        f' --comment comment=\"{metadata["commentary"] or version}\"',
        new,
        filename)
    return new, cmd


async def set_cmd(metadata, media, num, filename, opts):
    if media == 'flac':
        return await get_flac(metadata, num, filename, opts)
    elif media == 'opus':
        return await get_opus(metadata, num, filename, opts)
    elif media == 'vorbis':
        return await get_vorbis(metadata, num, filename, opts)
    elif media == 'mp3':
        return await get_mp3(metadata, num, filename, opts)


async def filter_tracks(template, res, junk, main_task):
    files = list()
    while not main_task.done():
        await asyncio.sleep(0.1)
        files = [item for item in sorted(glob.glob(f'{template}*.wav'))
                 if item not in junk and item not in res]
        if files and len(files) >= 2:
            res.append(files[0])
    res.append(files[0])


async def encode_tracks(metadata, res, main_task, media, opts):
    i = 0
    while not main_task.done() or res:
        if not len(res):
            await asyncio.sleep(0.1)
            continue
        new, cmd = await set_cmd(metadata, media, i, res[0], opts)
        p = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        await p.wait()
        os.remove(res[0])
        current = res.pop(0)
        print(f'{current} -> {new}')
        i += 1
