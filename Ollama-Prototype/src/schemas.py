from pydantic import BaseModel, Field

from typing import List, Literal, Optional, Dict


class CVFit(BaseModel):
    cv_id: str
    fit_score: float = Field(ge=0.0, le=1.0)
    invite: Literal["yes", "no"]
    strengths: List[str]
    gaps: List[str]
    reason: str

class RankingResult(BaseModel):
    ranking: List[CVFit]
    recommendation: dict
    notes: str




class UsageProfile(BaseModel):
    """Monthly usage (simple aggregated profile)."""
    data_gb: float = Field(ge=0)
    minutes: int = Field(ge=0)
    sms: int = Field(ge=0)
    roaming_gb: float = Field(default=0, ge=0)
    intl_minutes: int = Field(default=0, ge=0)


class Addon(BaseModel):
    addon_id: str
    name: str
    monthly_fee: float = Field(ge=0)
    adds_data_gb: float = Field(default=0, ge=0)
    adds_minutes: int = Field(default=0, ge=0)
    adds_sms: int = Field(default=0, ge=0)
    notes: str = ""


class PlanOffer(BaseModel):
    plan_id: str
    name: str
    monthly_fee: float = Field(ge=0)

    included_data_gb: float = Field(ge=0)
    included_minutes: int = Field(ge=0)
    included_sms: int = Field(ge=0)

    overage_per_gb: float = Field(ge=0)
    overage_per_minute: float = Field(ge=0)
    overage_per_sms: float = Field(ge=0)

    contract_months: int = Field(ge=0)
    network: str = ""
    notes: str = ""


class Catalog(BaseModel):
    plans: List[PlanOffer]
    addons: List[Addon] = []


class CurrentSubscription(BaseModel):
    plan_id: str
    addon_ids: List[str] = []


class CandidateAction(BaseModel):
    type: Literal["switch_plan", "add_addon", "remove_addon", "keep"]
    plan_id: Optional[str] = None
    addon_id: Optional[str] = None
    reason: str = Field(min_length=1, max_length=400)


class CandidateSet(BaseModel):
    candidates: List[CandidateAction] = Field(min_length=1, max_length=12)
    notes: str = ""


class EvaluationResult(BaseModel):
    action: CandidateAction
    predicted_monthly_cost: float
    breakdown: Dict[str, float]
    explanation: str = ""
