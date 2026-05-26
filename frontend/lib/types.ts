// TS shapes that mirror backend Pydantic schemas.

export type UserRole = "staff" | "owner";

export type Staff = {
  id: number;
  name: string;
  phone: string;
  role: UserRole;
};

export type AuthResponse = {
  token: string;
  staff: Staff;
};

export type Dog = {
  id: number;
  name: string;
  breed: string;
  age_years: number;
  weight_kg: number;
  diet: string | null;
  medications: string | null;
  allergies: string | null;
  vaccination_status: "up_to_date" | "expiring_soon" | "expired" | string;
  vaccination_expires: string | null;
  owner_name: string;
  owner_phone: string;
  vet_contact: string | null;
  notes: string | null;
};

export type Booking = {
  id: number;
  dog_id: number;
  start_date: string;
  end_date: string;
  status: "scheduled" | "checked_in" | "in_care" | "checked_out" | string;
  kennel_id: string | null;
  last_walked_at: string | null;
  last_fed_at: string | null;
  last_meds_at: string | null;
};

export type DogDetail = Dog & {
  current_booking: Booking | null;
  recent_incidents: Incident[];
};

export type Incident = {
  id: number;
  dog_id: number;
  staff_id: number;
  type: "health" | "behavior" | "feeding" | "other" | string;
  severity: "mild" | "moderate" | "severe" | string;
  description: string;
  created_at: string;
};

export type TodayBookingItem = {
  booking_id: number;
  dog: Dog;
  kennel_id: string | null;
  status: string;
  last_walked_at: string | null;
  last_fed_at: string | null;
  last_meds_at: string | null;
};

export type BookingsToday = {
  checking_in: TodayBookingItem[];
  in_care: TodayBookingItem[];
  checking_out: TodayBookingItem[];
};
