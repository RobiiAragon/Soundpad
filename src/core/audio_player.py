import pygame
from typing import List, Dict


class AudioPlayer:
    def __init__(self):
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.mixer.init()
        self.cache: Dict[str, pygame.mixer.Sound] = {}

    def preload(self, paths: List[str]):
        # remove stale entries
        for k in list(self.cache.keys()):
            if k not in paths:
                try:
                    del self.cache[k]
                except KeyError:
                    pass
        for p in paths:
            if p and p not in self.cache:
                try:
                    self.cache[p] = pygame.mixer.Sound(p)
                except Exception:
                    # ignore bad files
                    pass

    def play(self, path: str):
        if not path:
            return
        snd = self.cache.get(path)
        if not snd:
            try:
                snd = pygame.mixer.Sound(path)
                self.cache[path] = snd
            except Exception:
                return
        snd.play()

    def stop_all(self):
        try:
            pygame.mixer.stop()
        except Exception:
            pass
