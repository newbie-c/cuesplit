#!/usr/bin/env python3

import argparse
import asyncio
import json
import os
import re

from chardet import detect


def parse_args():
    args = argparse.ArgumentParser()
    args.add_argument(
        '-v', '--version', action='version', version='cuesplit-1.0.1-pre')
    args.add_argument(
        'filename', action='store', help='the converted file name')
    return args.parse_args()


async def check_dep(dependency):
    for path in os.getenv('PATH').split(':'):
        dep_bin = os.path.join(path, dependency)
        if os.path.exists(dep_bin):
            return True


async def make_couple(filename, res):
    medias = ('.wav', '.flac')
    cues = ('.cue', '.cue~')
    if not os.path.exists(filename):
        raise FileNotFoundError(f'"{filename}" does not exist')
    source = os.path.realpath(filename)
    hd = os.path.dirname(source)
    name, ext = os.path.splitext(os.path.basename(source))
    if ext in cues:
        for each in medias:
            m = os.path.join(hd, name + each)
            if os.path.exists(m):
                res['media'] = m
                res['cue'] = source
                break
    elif ext in medias:
        for each in cues:
            c = os.path.join(hd, name + each)
            if os.path.exists(c):
                res['cue'] = c
                res['media'] = source
                break


async def detect_f_type(name):
    required = 'file'
    dep = await check_dep(required)
    if not dep:
        raise OSError(f'{required} is not installed')
    p = await asyncio.create_subprocess_shell(
        f'file -b --mime-type "{name}"',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await p.communicate()
    if stderr:
        raise RuntimeError('something bad happened')
    return stdout.decode('utf-8').strip()


async def read_file(name):
    t = await detect_f_type(name)
    if t != 'text/plain':
        raise OSError('bad cue')
    try:
        with open(name, 'rb') as f:
            enc = detect(f.read())['encoding']
            f.seek(0)
            return [line.decode(enc).rstrip() for line in f]
    except(OSError, ValueError):
        return None


async def get_value(content, expression):
    pattern = re.compile(expression)
    for line in content:
        box = pattern.match(line)
        if box:
            return box.group(1).strip('"')


async def get_tracks(content):
    res = list()
    i = 0
    pattern = re.compile(r'^ +TRACK +(\d+) +(.+)')
    for step, item in enumerate(content):
        box = pattern.match(item)
        if box:
            track = dict()
            track['num'] = box.group(1)
            track['this'] = step
            if i:
                res[i - 1]['next'] = step
            res.append(track)
            i += 1
    return res


async def get_tracks_meta(content, tracks):
    for i in range(len(tracks)):
        title = re.compile(r'^ +TITLE +(.+)')
        perf = re.compile(r'^ +PERFORMER +(.+)')
        index0 = re.compile(r'^ +INDEX 00 +(\d{2}:\d{2}:\d{2})')
        index1 = re.compile(r'^ +INDEX 01 +(\d{2}:\d{2}:\d{2})')
        first = tracks[i].get('this')
        second = tracks[i].get('next')
        for line in content[first:second]:
            box = title.match(line)
            if box:
                tracks[i]['title'] = box.group(1).strip('"')
            box = perf.match(line)
            if box:
                tracks[i]['performer'] = box.group(1).strip('"')
            box = index0.match(line)
            if box:
                tracks[i]['index0'] = box.group(1)
            box = index1.match(line)
            if box:
                tracks[i]['index1'] = box.group(1)
        if first:
            del tracks[i]['this']
        if second:
            del tracks[i]['next']


async def extract_metadata(filename, res):
    content = await read_file(filename)
    if content is None:
        raise ValueError('cue is not readable or has bad encoding')
    res['album performer'] = await get_value(content, r'^PERFORMER +(.+)')
    res['album'] = await get_value(content, r'^TITLE +(.+)')
    res['genre'] = await get_value(content, r'REM GENRE +(.+)')
    res['disc ID'] = await get_value(content, r'^REM DISCID +(.+)')
    res['date'] = await get_value(content, r'^REM DATE +(.+)')
    res['comment'] = await get_value(content, r'^REM COMMENT +(.+)')
    res['tracks'] = await get_tracks(content)
    if res['tracks']:
        await get_tracks_meta(content, res['tracks'])


async def main(arguments):
    data = dict()
    await make_couple(arguments.filename, data)
    cue, media = data.get('cue'), data.get('media')
    if cue and media:
        await extract_metadata(cue, data)
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    cmd = parse_args()
    try:
        asyncio.run(main(cmd))
    except Exception as e:
        print(e)