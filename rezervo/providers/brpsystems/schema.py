import enum
from datetime import datetime
from enum import Enum
from typing import List, Optional, Union

import pytz
from pydantic import BaseModel

from rezervo.models import SessionState
from rezervo.schemas.config.user import IntegrationIdentifier
from rezervo.schemas.schedule import RezervoClass, RezervoInstructor, RezervoStudio


class BrpSubdomain(enum.Enum):
    TTT = "3t"
    FSC = "fsc"


# TODO: remove dependency on IntegrationIdentifier in this provider
SUBDOMAIN_TO_INTEGRATION_IDENTIFIER = {
    BrpSubdomain.TTT: IntegrationIdentifier.TTT,
    BrpSubdomain.FSC: IntegrationIdentifier.FSC,
}


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
    inWaitingList: int


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
    billingAddress: Optional[
        dict
    ] = None  # You can create a separate BillingAddress class if needed
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


def session_state_from_brp(booking_type: BookingType) -> SessionState:
    match booking_type:
        case BookingType.GROUP_ACTIVITY:
            return SessionState.BOOKED
        case BookingType.WAITING_LIST:
            return SessionState.WAITLIST
    return SessionState.UNKNOWN


def tz_aware_iso_from_brp_date_str(date: str) -> str:
    return pytz.UTC.localize(datetime.fromisoformat(date.replace("Z", ""))).isoformat()


# TODO: this should be replaced when timezones are handled properly
def human_iso_from_brp_date_str(date: str) -> str:
    return (
        pytz.UTC.localize(datetime.fromisoformat(date.replace("Z", "")))
        .astimezone(pytz.timezone("Europe/Oslo"))
        .replace(tzinfo=None)
        .isoformat()
        .replace("T", " ")
    )


def rezervo_class_from_brp_class(
    subdomain: BrpSubdomain, brp_class: BrpClass
) -> RezervoClass:
    return RezervoClass(
        integration=SUBDOMAIN_TO_INTEGRATION_IDENTIFIER[subdomain],
        id=brp_class.id,
        name=brp_class.groupActivityProduct.name,
        activityId=brp_class.groupActivityProduct.id,
        from_field=human_iso_from_brp_date_str(brp_class.duration.start),
        to=human_iso_from_brp_date_str(brp_class.duration.end),
        instructors=[RezervoInstructor(name=s.name) for s in brp_class.instructors],
        studio=RezervoStudio(
            id=brp_class.businessUnit.id,
            name=brp_class.businessUnit.name,
        ),
        userStatus=None,
        bookable=datetime.fromisoformat(
            tz_aware_iso_from_brp_date_str(brp_class.bookableEarliest)
        )
        < datetime.now().astimezone()
        < datetime.fromisoformat(
            tz_aware_iso_from_brp_date_str(brp_class.bookableLatest)
        ),
        bookingOpensAt=tz_aware_iso_from_brp_date_str(brp_class.bookableEarliest),
    )
