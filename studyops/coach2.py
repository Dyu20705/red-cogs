from .automation import StudyOps as OldStudyOps
from .studycoach import StudyCoachMixin


class StudyOps(StudyCoachMixin, OldStudyOps):
    def __init__(self, bot):
        super().__init__(bot)
        self._studycoach_init()

    def cog_unload(self):
        self._studycoach_unload()
        super().cog_unload()
