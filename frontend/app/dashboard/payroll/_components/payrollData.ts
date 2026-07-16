export interface PayrollEmployee {
  id:          string;
  name:        string;
  avatar:      string;
  dept:        string;
  designation: string;
  bank:        string;
  account:     string;
  ifsc:        string;
  basic:       number;
  hra:         number;
  da:          number;
  special:     number;
  bonus:       number;
  ot:          number;
  pf:          number;
  esi:         number;
  pt:          number;
  tds:         number;
  loan_emi:    number;
  advance:     number;
  lop:         number;
  travel:      number;
  fuel:        number;
  medical:     number;
  internet:    number;
  food:        number;
  incentive:   number;
  festival:    number;
  perf_bonus:  number;
  loan_total:  number;
  loan_rem:    number;
}

export const EMP_DATA: PayrollEmployee[] = [
  { id: "EMP001", name: "Arjun Mehta",  avatar: "AM", dept: "Engineering", designation: "Sr. Developer",   bank: "HDFC Bank",  account: "XXXX4521", ifsc: "HDFC0001234", basic: 45000, hra: 18000, da: 4500,  special: 6000,  bonus: 5000, ot: 2000, pf: 5400, esi: 315,  pt: 200, tds: 3500, loan_emi: 5000, advance: 0,    lop: 0,    travel: 2000, fuel: 0,    medical: 500,  internet: 500, food: 1000, incentive: 3000, festival: 0,    perf_bonus: 2000, loan_total: 60000, loan_rem: 40000 },
  { id: "EMP002", name: "Priya Sharma", avatar: "PS", dept: "HR",          designation: "HR Executive",     bank: "SBI",        account: "XXXX7812", ifsc: "SBIN0002345", basic: 35000, hra: 14000, da: 3500,  special: 4000,  bonus: 0,    ot: 0,    pf: 4200, esi: 245,  pt: 200, tds: 1500, loan_emi: 0,    advance: 2000, lop: 1167, travel: 1000, fuel: 0,    medical: 0,    internet: 500, food: 500,  incentive: 0,    festival: 0,    perf_bonus: 0,    loan_total: 0,     loan_rem: 0     },
  { id: "EMP003", name: "Rahul Singh",  avatar: "RS", dept: "Sales",       designation: "Sales Manager",    bank: "ICICI Bank", account: "XXXX9034", ifsc: "ICIC0003456", basic: 50000, hra: 20000, da: 5000,  special: 8000,  bonus: 8000, ot: 3000, pf: 6000, esi: 0,    pt: 200, tds: 6000, loan_emi: 0,    advance: 0,    lop: 0,    travel: 3000, fuel: 2000, medical: 1000, internet: 500, food: 1500, incentive: 5000, festival: 2000, perf_bonus: 3000, loan_total: 0,     loan_rem: 0     },
  { id: "EMP004", name: "Meena Iyer",   avatar: "MI", dept: "Finance",     designation: "Finance Analyst",  bank: "Axis Bank",  account: "XXXX6127", ifsc: "UTIB0004567", basic: 40000, hra: 16000, da: 4000,  special: 5000,  bonus: 0,    ot: 0,    pf: 4800, esi: 280,  pt: 200, tds: 2500, loan_emi: 8000, advance: 0,    lop: 0,    travel: 1500, fuel: 0,    medical: 500,  internet: 500, food: 1000, incentive: 0,    festival: 0,    perf_bonus: 1000, loan_total: 96000, loan_rem: 72000 },
  { id: "EMP005", name: "Suresh Kumar", avatar: "SK", dept: "Operations",  designation: "Ops Executive",    bank: "Kotak Bank", account: "XXXX3318", ifsc: "KKBK0005678", basic: 30000, hra: 12000, da: 3000,  special: 3000,  bonus: 0,    ot: 1500, pf: 3600, esi: 210,  pt: 200, tds: 500,  loan_emi: 5000, advance: 0,    lop: 0,    travel: 800,  fuel: 0,    medical: 0,    internet: 0,   food: 500,  incentive: 0,    festival: 0,    perf_bonus: 500,  loan_total: 60000, loan_rem: 50000 },
];

export function grossEarnings(e: PayrollEmployee): number {
  return e.basic + e.hra + e.da + e.special + e.bonus + e.ot;
}

export function totalDeductions(e: PayrollEmployee): number {
  return e.pf + e.esi + e.pt + e.tds + e.loan_emi + e.advance + e.lop;
}

export function totalReimb(e: PayrollEmployee): number {
  return e.travel + e.fuel + e.medical + e.internet + e.food;
}

export function netSalary(e: PayrollEmployee): number {
  return grossEarnings(e) - totalDeductions(e) + totalReimb(e);
}

export function fmt(n: number): string {
  return "₹" + n.toLocaleString("en-IN");
}
