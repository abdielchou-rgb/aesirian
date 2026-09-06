"""Gate registry - dynamically loads all gates."""

from __future__ import annotations
from .base import BaseGate

from .svt import SVT01_SingleSceneFlip, SVT02_ContinuousFlat, SVT03_ValueMonotone, SVT04_ActClimax
from .iit import IIT01_Timing, IIT02_DualDesire, IIT03_Irreversibility
from .ddt import DDT01_SingleDesire, DDT02_DesireOverexposed, DDT03_ProgressTooSmooth, DDT04_DesireLatentTooLong
from .gda import GDA01_GapFamine, GDA02_GapOverload, GDA03_GapMonotone, GDA04_GapDesert
from .clm import CLM01_SingleLayer, CLM02_NoCrossover, CLM03_Mismatch
from .rvi import RVI01_CuriosityStarvation, RVI02_FrustrationBuildup, RVI03_DeusExMachina, RVI04_GapOverload, RVI05_GapForgotten
from .tpe import TPE01_OverexplainedEmotion, TPE02_TurnNoTouchpoint, TPE03_TouchpointMismatch
from .prp import PRP01_TemplateMismatch, PRP02_HookOverdue, PRP03_ClimaxGap
from .nfr import NFR01_CoreSettingRecap, NFR02_CharacterGoalRestatement, NFR03_ForeshadowRepeat, NFR04_JumpReaderAnchor, NFR05_SubtextLayer
from .rashomon import RSM01_PovBeliefSystem, RSM02_UnresolvedContradiction, RSM03_OverlapBoundary
from .pleasure import PLE01_PleasurePointDensity, PLE02_SuppressionRelease, PLE03_FaceSlapStructure, PLE04_UpgradeChain, PLE05_ShowingOff, PLE06_PayoffRatio
from .golden3 import G3_01_FirstChapterConflict, G3_02_ProtagonistIntro, G3_03_WhyQuestion, G3_04_Chapter2Goal, G3_05_Chapter3Pleasure, G3_06_Chapter3Cliffhanger, G3_07_NoInfoDump
from .quality import QLT01_FillerDetection, QLT02_RepeatedInfo, QLT03_EmotionCurve, QLT04_PacingVariety, QLT05_OpenLoopCount
from .dialogue import DLG01_DialogueFunction, DLG02_Subtext, DLG03_DialogueRhythm, DLG04_InfoDumpDialogue, DLG05_CharacterVoice, DLG06_ActionInterrupt
from .suspense import SPN01_TensionEscalation, SPN02_SuspenseDensity, SPN03_PeakBeforeRelease, SPN04_MultipleSuspense
from .break_chapter import BRK01_ChapterEndHook, BRK02_BreakTiming, BRK03_ChapterLength, BRK04_FiveWHook
from .scene_sequel import SCQ01_SceneStructure, SCQ02_SequelStructure, SCQ03_SceneSequelAlternation, SCQ04_MotivationReaction, SCQ05_ProactiveProtagonist
from .romance import ROE01_EmotionalTension, ROE02_SweetBitterRatio, ROE03_CPChemistry, ROE04_MisunderstandingCycle, ROE05_DetailSugar, ROE06_LoveRivalDensity
from .micro_tension import MT01_MicroTensionDensity, MT02_ReversalDensity
from .char_relation import CRN01_RelationshipCount, CRN02_RelationDiversity, CRN03_RelationshipEvolution, CRN04_CharacterTriangle, CRN05_OpponentDepth
from .more_gates import *
from .master_gates import BRK01B_HookDistribution, QLT01B_FillerDetection, BRK04B_BreakPosition, IIT04_Midpoint, IIT05_AllIsLost, STR07_ThemeProved, DLG07_BStory, RVI06_EvilForceReveal, CRN06_OpponentNetwork, PLE07_UpgradeRhythm, QLT06_PayWallCheck
from .arches import ARC01_ScarReveal, ARC02_DesireConflict, ARC03_WeaknessCost, ARC04_Transformation, ARC05_LengthAwarePacing, ARC06_PayoffDelay, ARC07_TurnQuality, ARC08_ChapterBreak, ARC09_DepthCheck
from .structure import STR01_ChapterHook, STR02_SceneObjective, STR03_SceneStructure, STR04_SevenLayerRhythm, STR05_SceneRemovability, STR06_ChapterLengthConsistency
from .language import LANG01_MRUChain, LANG02_POVDiscipline, LANG03_AdverbCheck, LANG04_PassiveVoice, LANG05_FillerWords
from .craft_gates import (
    DRM01_FourDomainDiagnosis, DRM02_LogicContradiction,
    HOL01_MidpointType,
    NEU01_StakePresence, NEU02_EmpathyTrigger, NEU03_ExpectedSurprise,
    TRB01_MoralArgument,
    WNM01_BreakTypeCategory,
    G10_04_WorldExpansion, G10_05_FirstMiniClimax, G10_07_ProactiveAction,
    G10_08_OpponentIntro, G10_09_FirstFailure, G10_10_FirstUpgrade,
)
from .style_consistency import (
    STC01_AdverbDrift, STC02_PassiveDrift, STC03_FillerAdverbRatio,
    STC04_VocabDiversityDrop, STC05_DifficultWordSpike, STC06_EmotionWordDrift,
    STC07_SentenceLengthVariance, STC08_SentenceLengthDrift, STC09_MAXSentenceRatio,
    STC10_DialogueDensityDrift, STC11_ParagraphLengthDrift,
    STC12_ChapterEndpointForce, STC13_HookDensityDrift, STC14_GapDensityDrift,
    STC15_GenreFitDecline,
    STC16_SentimentCoherence, STC17_ActStructureTransition, STC18_RhythmScoreDecline,
    STC19_PosEntropyChange, STC20_EmotionTensionMismatch,
    STC21_OverallDriftScore, STC22_ConsecutiveDriftChapters,
)

ALL_GATES = {}
ALL_GATES.update({
    "SVT-01": SVT01_SingleSceneFlip, "SVT-02": SVT02_ContinuousFlat,
    "SVT-03": SVT03_ValueMonotone, "SVT-04": SVT04_ActClimax,
    "IIT-01": IIT01_Timing, "IIT-02": IIT02_DualDesire, "IIT-03": IIT03_Irreversibility,
    "DDT-01": DDT01_SingleDesire, "DDT-02": DDT02_DesireOverexposed,
    "DDT-03": DDT03_ProgressTooSmooth, "DDT-04": DDT04_DesireLatentTooLong,
    "GDA-01": GDA01_GapFamine, "GDA-02": GDA02_GapOverload,
    "GDA-03": GDA03_GapMonotone, "GDA-04": GDA04_GapDesert,
    "CLM-01": CLM01_SingleLayer, "CLM-02": CLM02_NoCrossover, "CLM-03": CLM03_Mismatch,
    "RVI-01": RVI01_CuriosityStarvation, "RVI-02": RVI02_FrustrationBuildup,
    "RVI-03": RVI03_DeusExMachina, "RVI-04": RVI04_GapOverload, "RVI-05": RVI05_GapForgotten,
    "TPE-01": TPE01_OverexplainedEmotion, "TPE-02": TPE02_TurnNoTouchpoint, "TPE-03": TPE03_TouchpointMismatch,
    "PRP-01": PRP01_TemplateMismatch, "PRP-02": PRP02_HookOverdue, "PRP-03": PRP03_ClimaxGap,
    "NFR-01": NFR01_CoreSettingRecap, "NFR-02": NFR02_CharacterGoalRestatement,
    "NFR-03": NFR03_ForeshadowRepeat, "NFR-04": NFR04_JumpReaderAnchor, "NFR-05": NFR05_SubtextLayer,
    "RSM-01": RSM01_PovBeliefSystem, "RSM-02": RSM02_UnresolvedContradiction, "RSM-03": RSM03_OverlapBoundary,
    "PLE-01": PLE01_PleasurePointDensity, "PLE-02": PLE02_SuppressionRelease,
    "PLE-03": PLE03_FaceSlapStructure, "PLE-04": PLE04_UpgradeChain, "PLE-05": PLE05_ShowingOff, "PLE-06": PLE06_PayoffRatio,
    "G3-01": G3_01_FirstChapterConflict, "G3-02": G3_02_ProtagonistIntro,
    "G3-03": G3_03_WhyQuestion, "G3-04": G3_04_Chapter2Goal, "G3-05": G3_05_Chapter3Pleasure,
    "G3-06": G3_06_Chapter3Cliffhanger, "G3-07": G3_07_NoInfoDump,
    "QLT-01": QLT01_FillerDetection, "QLT-02": QLT02_RepeatedInfo,
    "QLT-03": QLT03_EmotionCurve, "QLT-04": QLT04_PacingVariety, "QLT-05": QLT05_OpenLoopCount,
    "SCQ-01": SCQ01_SceneStructure, "SCQ-02": SCQ02_SequelStructure,
    "SCQ-03": SCQ03_SceneSequelAlternation, "SCQ-04": SCQ04_MotivationReaction, "SCQ-05": SCQ05_ProactiveProtagonist,
    "ROE-01": ROE01_EmotionalTension, "ROE-02": ROE02_SweetBitterRatio,
    "ROE-03": ROE03_CPChemistry, "ROE-04": ROE04_MisunderstandingCycle, "ROE-05": ROE05_DetailSugar, "ROE-06": ROE06_LoveRivalDensity,
    "MTS-01": MT01_MicroTensionDensity, "MTS-02": MT02_ReversalDensity,
    "CRN-01": CRN01_RelationshipCount, "CRN-02": CRN02_RelationDiversity,
    "CRN-03": CRN03_RelationshipEvolution, "CRN-04": CRN04_CharacterTriangle, "CRN-05": CRN05_OpponentDepth,
    "DLG-01": DLG01_DialogueFunction, "DLG-02": DLG02_Subtext,
    "DLG-03": DLG03_DialogueRhythm, "DLG-04": DLG04_InfoDumpDialogue, "DLG-05": DLG05_CharacterVoice, "DLG-06": DLG06_ActionInterrupt,
    "SPN-01": SPN01_TensionEscalation, "SPN-02": SPN02_SuspenseDensity,
    "SPN-03": SPN03_PeakBeforeRelease, "SPN-04": SPN04_MultipleSuspense,
    "BRK-01": BRK01_ChapterEndHook, "BRK-02": BRK02_BreakTiming,
    "BRK-03": BRK03_ChapterLength, "BRK-04": BRK04_FiveWHook,
    "CTP-01": CTP01_SceneObjective, "CTP-02": CTP02_SubtextInScene,
    "CTB-01": CTB01_CausalityChain, "CTB-02": CTB02_PayoffTracking,
    "PRC-01": PRC01_ShowDontTell, "PRC-02": PRC02_PacingVariety,
    "MCO-01": MCO01_EventDensity, "MCO-02": MCO02_SceneTransition,
    "APL-01": APL01_OpeningHook, "APL-02": APL02_EndingResolution,
    "MRD-01": MRD01_SentenceVariety, "MRD-02": MRD02_ParagraphLength,
    "INR-01": INR01_NarrativeFocus,
    "BRK-01B": BRK01B_HookDistribution, "QLT-01B": QLT01B_FillerDetection,
    "BRK-04B": BRK04B_BreakPosition, "IIT-04": IIT04_Midpoint,
    "IIT-05": IIT05_AllIsLost, "STR-07": STR07_ThemeProved,
    "DLG-07": DLG07_BStory, "RVI-06": RVI06_EvilForceReveal,
    "CRN-06": CRN06_OpponentNetwork, "PLE-07": PLE07_UpgradeRhythm,
    "QLT-06": QLT06_PayWallCheck,
    "DRM-01": DRM01_FourDomainDiagnosis, "DRM-02": DRM02_LogicContradiction,
    "HOL-01": HOL01_MidpointType,
    "NEU-01": NEU01_StakePresence, "NEU-02": NEU02_EmpathyTrigger, "NEU-03": NEU03_ExpectedSurprise,
    "TRB-01": TRB01_MoralArgument,
    "WNM-01": WNM01_BreakTypeCategory,
    "G10-04": G10_04_WorldExpansion, "G10-05": G10_05_FirstMiniClimax,
    "G10-07": G10_07_ProactiveAction, "G10-08": G10_08_OpponentIntro,
    "G10-09": G10_09_FirstFailure, "G10-10": G10_10_FirstUpgrade,
    "ARC-01": ARC01_ScarReveal, "ARC-02": ARC02_DesireConflict,
    "ARC-03": ARC03_WeaknessCost, "ARC-04": ARC04_Transformation, "ARC-05": ARC05_LengthAwarePacing,
    "ARC-06": ARC06_PayoffDelay, "ARC-07": ARC07_TurnQuality, "ARC-08": ARC08_ChapterBreak, "ARC-09": ARC09_DepthCheck,
    "STR-01": STR01_ChapterHook, "STR-02": STR02_SceneObjective,
    "STR-03": STR03_SceneStructure, "STR-04": STR04_SevenLayerRhythm, "STR-05": STR05_SceneRemovability, "STR-06": STR06_ChapterLengthConsistency,
    "LANG-01": LANG01_MRUChain, "LANG-02": LANG02_POVDiscipline,
    "LANG-03": LANG03_AdverbCheck, "LANG-04": LANG04_PassiveVoice, "LANG-05": LANG05_FillerWords,
    # v4.2: 风格一致性门禁 (22)
    "STC-01": STC01_AdverbDrift, "STC-02": STC02_PassiveDrift,
    "STC-03": STC03_FillerAdverbRatio, "STC-04": STC04_VocabDiversityDrop,
    "STC-05": STC05_DifficultWordSpike, "STC-06": STC06_EmotionWordDrift,
    "STC-07": STC07_SentenceLengthVariance, "STC-08": STC08_SentenceLengthDrift,
    "STC-09": STC09_MAXSentenceRatio, "STC-10": STC10_DialogueDensityDrift,
    "STC-11": STC11_ParagraphLengthDrift, "STC-12": STC12_ChapterEndpointForce,
    "STC-13": STC13_HookDensityDrift, "STC-14": STC14_GapDensityDrift,
    "STC-15": STC15_GenreFitDecline,
    "STC-16": STC16_SentimentCoherence, "STC-17": STC17_ActStructureTransition,
    "STC-18": STC18_RhythmScoreDecline, "STC-19": STC19_PosEntropyChange,
    "STC-20": STC20_EmotionTensionMismatch,
    "STC-21": STC21_OverallDriftScore, "STC-22": STC22_ConsecutiveDriftChapters,
})

BLOCKING_GATES = {k: v for k, v in ALL_GATES.items() if v().severity.value == "block"}

def get_gate(gate_id: str) -> BaseGate:
    cls = ALL_GATES.get(gate_id)
    if cls is None: raise ValueError(f"Unknown gate: {gate_id}")
    return cls()

def list_gates(severity: str = None) -> list[dict]:
    results = []
    for gid, cls in ALL_GATES.items():
        g = cls()
        if severity and g.severity.value != severity: continue
        results.append({"gate_id": g.gate_id, "name": g.name, "description": g.description, "severity": g.severity.value})
    return results