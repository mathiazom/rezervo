from datetime import datetime
from enum import Enum
from typing import List, Optional, TypeAlias, Union

import pytz
from pydantic import BaseModel

from rezervo.models import SessionState

BrpSubdomain: TypeAlias = str


BrpLocationIdentifier: TypeAlias = int


class BrpAuthResult(BaseModel):
    username: str
    roles: List[str]
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


class BrpClass(BaseModel):
    id: int
    name: str
    duration: Duration
    groupActivityProduct: GroupActivityProduct
    businessUnit: BusinessUnit
    locations: List[Location]
    instructors: List[Instructor]
    bookableEarliest: str
    bookableLatest: str
    externalMessage: Optional[str] = None
    internalMessage: Optional[str] = None
    cancelled: bool
    slots: Slots


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
    assets: Optional[List[BrpActivityAsset]] = None


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
    id: int
    number: str
    externalId: Optional[str]
    lastModified: str


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
    consents: List[Consent]
    temporary: Optional[Union[int, str]] = None  # Type based on actual usage
    lastPasswordChangedTime: str


def session_state_from_brp(
    booking_type: BookingType, checked_in: Optional[str]
) -> SessionState:
    if checked_in is not None:
        return SessionState.CONFIRMED

    match booking_type:
        case BookingType.GROUP_ACTIVITY:
            return SessionState.BOOKED
        case BookingType.WAITING_LIST:
            return SessionState.WAITLIST
    return SessionState.UNKNOWN


def tz_aware_iso_from_brp_date_str(date: str) -> str:
    return pytz.UTC.localize(datetime.fromisoformat(date.replace("Z", ""))).isoformat()
