# This file is part of the qpageview package.
#
# Copyright (c) 2016 - 2019 by Wilbert Berendsen
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
# See http://www.gnu.org/licenses/ for more information.

"""
Cache logic.
"""

import weakref
import time


class ImageEntry:
    
    replace = False
    
    def __init__(self, image):
        self.image = image
        self.bcount = image.byteCount()
        self.time = time.time()


class ImageCache:
    """Cache generated images.

    Store and retrieve them under a key (see render.Renderer.key()).
    
    The ImageCache object can be used as a dict().

    """
    maxsize = 209715200 # 200M
    currentsize = 0

    def __init__(self):
        self._cache = weakref.WeakKeyDictionary()

    def clear(self):
        """Remove all cached images."""
        self._cache.clear()
        self.currentsize = 0
    
    def invalidate(self, page=None):
        """Set the replace flag for all cached images to True.
        
        If the page is given, only images for that page will be set to replace.
        
        Images will still be returned on request, but the renderer will 
        reschedule a rendering of a new image. This way one can update render 
        options or page contents and get a smooth redraw without flickering an 
        empty page in between.
        
        """
        def keyds():
            if page:
                try:
                    yield self._cache[page.group()][page.ident()]
                except KeyError:
                    return
            else:
                for identd in self._cache.values():
                    for keyd in identd.values():
                        yield keyd
        for keyd in keyds():
            for tiled in keyd.values():
                for entry in tiled.values():
                    entry.replace = True


    def tileset(self, key):
        """Return a dictionary with tile-entry pairs for the key.
        
        If no single tile is available, an empty dict is returned.
        
        """
        try:
            return self._cache[key.group][key.ident][key[2:]]
        except KeyError:
            return {}
    
    def addtile(self, key, tile, image):
        """Add image for the specified key and tile."""
        d = self._cache.setdefault(key.group, {}).setdefault(key.ident, {}).setdefault(key[2:], {})
        try:
            self.currentsize -= d[tile].bcount
        except KeyError:
            pass
        
        purgeneeded = self.currentsize > self.maxsize

        e = d[tile] = ImageEntry(image)
        self.currentsize += e.bcount
    
        if not purgeneeded:
            return

        # purge old images if needed,
        # cache groups may have disappeared so count all images
        
        items = []
        items.extend(sorted(
            (entry.time, entry.bcount, group, ident, key, tile)
            for group, identd in self._cache.items()
                for ident, keyd in identd.items()
                    for key, tiled in sorted(keyd.items(), key=lambda i: i[0][1])[1:]
                        for tile, entry in tiled.items()))
        # smallest for each page last
        items.extend(sorted(
            (entry.time, entry.bcount, group, ident, key, tile)
            for group, identd in self._cache.items()
                for ident, keyd in identd.items()
                    for key, tiled in sorted(keyd.items(), key=lambda i: i[0][1])[:1]
                        for tile, entry in tiled.items()))
        
        # now count the newest images until maxsize ...
        items = reversed(items)
        currentsize = 0
        for time, bcount, group, ident, key, tile in items:
            currentsize += bcount
            if currentsize > self.maxsize:
                break
        self.currentsize = currentsize
        # ... and delete the remaining images, deleting empty dicts as well
        for time, bcount, group, ident, key, tile in items:
            del self._cache[group][ident][key][tile]
            if not self._cache[group][ident][key]:
                del self._cache[group][ident][key]
                if not self._cache[group][ident]:
                    del self._cache[group][ident]
                    if not self._cache[group]:
                        del self._cache[group]

    def closest(self, key):
        """Iterate over suitable image tilesets but with a different size.
        
        Yields (width, height, tileset) tuples.
        
        This can be used for interim display while the real image is being
        rendered.

        """
        # group and ident must be there.
        try:
            keyd = self._cache[key.group][key.ident]
        except KeyError:
            return ()
        
        suitable = [
            (k[1], k[2], tileset)
            for k, tileset in keyd.items()
                if k[0] == key.rotation and k[1] != key.width
                    and not any(e.replace for e in tileset.values())]
        return sorted(suitable, key=lambda s: abs(1 - s[0] / key.width))


