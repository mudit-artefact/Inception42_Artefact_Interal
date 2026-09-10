/**
 * The questions offered on an empty conversation.
 *
 * Real copy, and the only thing worth keeping out of `lib/api/mock.ts` when that file was
 * deleted. Everything else in it was invented data standing in for a backend that was not
 * answering: twelve personas who predated the six new joiners and carried no employment
 * status, and a chat that replied "Annual Leave: 12 of 21 days remaining" — a balance
 * nobody held, cited to policy numbers this company does not use.
 *
 * These are questions, not answers. They are put to the assistant like any other, and what
 * comes back is read from the People Code.
 */
export const SUGGESTED_QUESTIONS: string[] = [
  "Can I take work from home?",
  "Who is my line manager?",
  "Can I carry over unused leave into next year?",
  "What are the core working hours and attendance policy?",
  "When do I need to submit a medical certificate for sick leave?",
  "How does the child education allowance policy work?",
];
