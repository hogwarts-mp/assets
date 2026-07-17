-- Make the substrate's advertised quests unavailable (journal entries + world markers).
-- ZZC_01 = Charms Class, ZZD_01 = DADA Class, COM_02 = Like a Moth to a Frame,
-- DayOneTime = Attend Your First Day scheduler. Verified in-game 2026-07-05.
DELETE FROM MissionDynamic WHERE Type='MissionEntryPoint' AND MissionID IN ('ZZC_01','ZZD_01','COM_02');
UPDATE MissionDynamic SET Text2='Invalid' WHERE Type='Main' AND MissionID IN ('ZZC_01','ZZD_01','COM_02','DayOneTime');
