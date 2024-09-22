from datetime import datetime
from enum import Enum
from typing import Optional, TypeAlias, Union

import pytz
from pydantic import BaseModel, ConfigDict

from rezervo.models import SessionState

BrpSubdomain: TypeAlias = str


BrpLocationIdentifier: TypeAlias = int


class BrpAuthData(BaseModel):
    username: str
    roles: list[str]
    token_type: str
    access_token: str
    expires_in: int
    refresh_token: str


class Duration(BaseModel):
    start: str
    end: str


class GroupActivityProduct(BaseModel):
    id: int
    name: str


class BusinessUnit(BaseModel):
    id: int
    name: str
    location: str
    companyNameForInvoice: str


class Location(BaseModel):
    id: int
    name: str


class Instructor(BaseModel):
    id: int
    name: str
    isSubstitute: bool


class Slots(BaseModel):
    total: int
    totalBookable: int
    reservedForDropin: int
    leftToBook: int
    leftToBookIncDropin: int  # also known as leftToBookIncludingDropIn
    hasWaitingList: bool
    inWaitingList: Optional[int] = None


class BaseBrpClass(BaseModel):
    id: int
    name: str
    duration: Duration
    groupActivityProduct: GroupActivityProduct
    businessUnit: BusinessUnit
    locations: list[Location]
    instructors: list[Instructor]
    externalMessage: Optional[str] = None
    internalMessage: Optional[str] = None
    cancelled: bool
    slots: Slots


class RawBrpClass(BaseBrpClass):
    """
    used to parse the raw JSON response from the BRP API
    useful for handling known malformed or sparse classes that are
    always dropped and never "promoted" to proper BrpClass instances
    """

    bookableEarliest: Optional[str] = None
    bookableLatest: Optional[str] = None


class BrpClass(BaseBrpClass):
    bookableEarliest: str
    bookableLatest: str


class BrpActivityAsset(BaseModel):
    # reference: str
    # \type: str
    # contentType: str
    contentUrl: str
    # imageWidth: int
    # imageHeight: int
    # focalPointX: int
    # focalPointY: int


class BrpReceivedActivityDetails(BaseModel):
    id: int
    description: Optional[str] = None
    assets: Optional[list[BrpActivityAsset]] = None


class BrpActivityDetails(BaseModel):
    description: str
    image_url: Optional[str] = None


class DetailedBrpClass(BrpClass):
    activity_details: BrpActivityDetails


class Customer(BaseModel):
    id: int
    firstName: str
    lastName: str


class GroupActivity(BaseModel):
    id: int
    name: str


class WaitingListBooking(BaseModel):
    id: int
    waitingListPosition: int


class Order(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)
    id: int
    number: str
    externalId: Optional[str] = None
    lastModified: Optional[str] = None


class GroupActivityBooking(BaseModel):
    id: int
    order: Order


class BookingType(Enum):
    WAITING_LIST = "waitingListBooking"
    GROUP_ACTIVITY = "groupActivityBooking"


class BookingData(BaseModel):
    type: BookingType
    groupActivity: GroupActivity
    businessUnit: BusinessUnit
    customer: Customer
    duration: Duration
    waitingListBooking: Optional[WaitingListBooking] = None
    groupActivityBooking: Optional[GroupActivityBooking] = None
    additionToEventBooking: Optional[object] = None
    checkedIn: Optional[str] = None


class Country(BaseModel):
    id: int
    name: str
    alpha2: str


class ShippingAddress(BaseModel):
    postalCode: str
    city: str
    street: str
    careOf: str
    country: Country


class MobilePhone(BaseModel):
    number: str
    countryCode: int


class CustomerType(BaseModel):
    id: int
    name: str


class ProfileImage(BaseModel):
    id: int


class Consent(BaseModel):
    id: int
    name: str


class UserDetails(BaseModel):
    id: int
    firstName: str
    lastName: str
    sex: str
    ssn: Optional[str] = None
    birthDate: str
    shippingAddress: ShippingAddress
    billingAddress: Optional[dict] = (
        None  # You can create a separate BillingAddress class if needed
    )
    email: str
    mobilePhone: MobilePhone
    businessUnit: BusinessUnit  # Reusing existing BusinessUnit schema
    customerType: CustomerType
    customerTypeEndDate: Optional[str] = None
    customerNumber: str
    cardNumber: str
    acceptedBookingTerms: bool
    acceptedSubscriptionTerms: bool
    acceptedRegistrationTerms: str
    profileImage: ProfileImage
    benefitStatus: Optional[Union[int, str]] = None  # Type based on actual usage
    memberJoinDate: str
    allowMassSendEmail: bool
    allowMassSendMail: bool
    allowMassSendSms: bool
    consents: list[Consent]
    temporary: Optional[Union[int, str]] = None  # Type based on actual usage
    lastPasswordChangedTime: str


def session_state_from_brp(
    booking_type: BookingType, start_time: datetime, checked_in: Optional[str]
) -> SessionState:
    if checked_in is not None:
        return SessionState.CONFIRMED

    # TODO: check if a direct 'noshow' status can be obtained from brp
    if start_time < datetime.now(tz=start_time.tzinfo):
        return SessionState.NOSHOW

    match booking_type:
        case BookingType.GROUP_ACTIVITY:
            return SessionState.BOOKED
        case BookingType.WAITING_LIST:
            return SessionState.WAITLIST
    return SessionState.UNKNOWN


def tz_aware_iso_from_brp_date_str(date: str) -> str:
    return pytz.UTC.localize(datetime.fromisoformat(date.replace("Z", ""))).isoformat()
