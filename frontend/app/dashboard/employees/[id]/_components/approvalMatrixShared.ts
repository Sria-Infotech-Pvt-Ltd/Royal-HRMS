export interface PickerEmployee {
  id:          string;
  full_name:   string;
  employee_id: string;
  department:  string;
  branch:      string;
}

export const SELECT_CLS =
  "w-full px-3.5 py-[7px] rounded-md border text-[13px] outline-none transition-all bg-[var(--surface)] appearance-none cursor-pointer" +
  " focus:border-[var(--primary)] focus:ring-2 focus:ring-[rgba(124,58,237,0.10)]";
const CHEVRON = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%234f5d75' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'/></svg>")`;
export const SELECT_STYLE = {
  borderColor: "#d3dae8",
  backgroundImage: CHEVRON,
  backgroundRepeat: "no-repeat" as const,
  backgroundPosition: "right 10px center" as const,
  backgroundSize: "15px",
  paddingRight: "2.5rem",
};
