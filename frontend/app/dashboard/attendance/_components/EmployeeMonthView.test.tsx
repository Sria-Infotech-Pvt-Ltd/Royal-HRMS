// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";

const TODAY = "2026-11-18";
const EMPLOYEES = [
  { id: "u1", employee_id: "EMP001", full_name: "Asha Rao", department: "Finance", designation: "Analyst" },
  { id: "u2", employee_id: "EMP002", full_name: "Durga Gadde", department: "Sales", designation: "Associate" },
  { id: "u3", employee_id: "EMP003", full_name: "Kabir Rao", department: "Web", designation: "Developer" },
];

const day = (n: number, status: string, extra: Record<string, unknown> = {}) => {
  const date = `2026-11-${String(n).padStart(2, "0")}`;
  return {
    date, day_short: "", day_num: n, status, status_label: status, clock_in: null, clock_out: null, total_hours: 0, is_flagged: false,
    record_id: ["present", "late", "half_day", "on_leave"].includes(status) ? `rec-${n}` : null, ...extra,
  };
};
const MONTH = {
  employee: EMPLOYEES[1], month: "2026-11", stats: { present: 2, late: 1, half_day: 0, absent: 1, on_leave: 0, lop_days: 1, total_hours: 26.5 },
  days: [
    day(2, "present", { clock_in: "09:05", clock_out: "18:10", total_hours: 9.1 }), day(3, "late", { clock_in: "09:40", clock_out: "18:00", total_hours: 8.3, is_flagged: true }),
    day(4, "present", { clock_in: "09:00", clock_out: "18:00", total_hours: 9 }), day(5, "absent"), day(7, "weekly_off"), day(9, "no_record"),
    day(18, "no_record"), day(25, "no_record"),
  ],
};

vi.mock("@/hooks/usePermission", () => ({ usePermission: () => mock.mayMark }));
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string | null) => {
    if (!url) return { data: null, loading: false, error: null, refetch: vi.fn() };
    if (url.includes("employee-calendar") || url.includes("calendar")) return mock.loadingMonth ? { data: null, loading: true, error: null, refetch: refetchSpy } : { data: MONTH, loading: false, error: null, refetch: refetchSpy };
    return mock.loadingEmployees ? { data: null, loading: true, error: null, refetch: vi.fn() } : { data: { results: EMPLOYEES }, loading: false, error: null, refetch: vi.fn() };
  },
}));
vi.mock("./AttendanceDetailDrawer", () => ({ default: ({ recordId }: { recordId: string }) => <div data-testid="detail">{recordId}</div> }));
vi.mock("./AttendanceEditForm", () => ({ AttendanceCreateForm: ({ date }: { date: string }) => <div data-testid="mark-form">{date}</div> }));
vi.mock("@/components/EmptyState", () => ({ default: ({ title, description }: { title: string; description?: string }) => <div><h3>{title}</h3>{description && <p>{description}</p>}</div> }));
vi.mock("@/lib/api/endpoints", () => ({ API: { employees: { list: "/employees/", detail: (id: string) => `/employees/${id}/` }, attendance: { employeeCalendar: (id: string, month: string) => `/attendance/calendar/${id}/${month}` } } }));

const refetchSpy = vi.fn();
const mock = vi.hoisted(() => ({ mayMark: true, loadingMonth: false, loadingEmployees: false }));

import EmployeeMonthView from "./EmployeeMonthView";

beforeEach(() => { vi.useFakeTimers({ toFake: ["Date"] }); vi.setSystemTime(new Date(2026, 10, 18, 10, 0)); refetchSpy.mockClear(); mock.mayMark = true; mock.loadingMonth = false; mock.loadingEmployees = false; });
afterEach(() => { cleanup(); vi.useRealTimers(); });

const openDropdown = () => fireEvent.click(screen.getByRole("button", { name: /Select an employee|\(EMP\d+\)/ }));

function chooseEmployee(name = "Durga") {
  openDropdown();
  fireEvent.change(screen.getByPlaceholderText("Search by name or ID…"), { target: { value: name } });
  fireEvent.click(screen.getByText("Durga Gadde (EMP002)"));
}

const PURPLE = /124,\s*58,\s*237|#7C3AED/i;
const GREEN = /22,\s*163,\s*74/;
const RGB = {
  present: /22,\s*163,\s*74/, late: /234,\s*88,\s*12/, absent: /220,\s*38,\s*38/, notMarked: /100,\s*116,\s*139/, weekOff: /148,\s*163,\s*184/,
};

describe("Calendar colours", () => {
  function open() { render(<EmployeeMonthView initialMonth="2026-11" />); chooseEmployee(); }

  it("tints each day in its status colour, with a coloured edge and a solid status label", () => {
    open();
    const present = screen.getByRole("button", { name: /^2 November: Present/i });
    expect(present.style.borderLeft).toMatch(RGB.present);
    expect(present.style.backgroundColor).toMatch(/22,\s*163,\s*74/);         // the green tint
    expect(within(present).getByText("Present").style.background).toMatch(RGB.present);
    expect(within(present).getByText("Present").style.color).toBe("rgb(255, 255, 255)");
    const late = screen.getByRole("button", { name: /^3 November: Late/i });
    expect(late.style.borderLeft).toMatch(RGB.late);
    const absent = screen.getByRole("button", { name: /^5 November: Absent/i });
    expect(absent.style.borderLeft).toMatch(RGB.absent);
    expect(within(absent).getByText("Absent").style.background).toMatch(RGB.absent);
  });

  it("shows a past day with nothing recorded as Not marked in slate with an outlined label, never amber or brown", () => {
    open();
    const notMarked = screen.getByRole("button", { name: /^9 November: Not marked/i });
    expect(notMarked.style.borderLeft).toMatch(/transparent/);                 // neutral: no coloured edge, so a month of them is not a wall of colour
    const label = within(notMarked).getByText("Not marked");
    expect(label.style.border).toMatch(/dashed/);
    expect(label.style.border).toMatch(RGB.notMarked);
    expect(label.style.color).toMatch(RGB.notMarked);
    expect(label.style.backgroundColor === "transparent" || label.style.background === "transparent").toBe(true);
  });

  it("no status uses a warm amber, olive or brown", () => {
    const warm = ["#ca8a04", "#b45309", "#d97706", "#b45f06", "#92400e", "#a16207"];
    open();
    const everyStyle = Array.from(document.querySelectorAll<HTMLElement>("[style]")).map(element => element.getAttribute("style") ?? "").join(" ").toLowerCase();
    for (const colour of warm) expect(everyStyle).not.toContain(colour);
    for (const [red, green, blue] of [[202, 138, 4], [180, 83, 9], [217, 119, 6]]) {
      expect(everyStyle).not.toContain(`rgb(${red}, ${green}, ${blue}`);
      expect(everyStyle).not.toContain(`rgba(${red}, ${green}, ${blue}`);
      expect(everyStyle).not.toContain(`rgba(${red},${green},${blue}`);
    }
  });

  it("stripes a week off and keeps an upcoming day grey and label-free", () => {
    open();
    const weekOff = screen.getByText("Week Off", { selector: "span" }).closest("button, div") as HTMLElement;
    expect(weekOff.style.borderLeft).toMatch(RGB.weekOff);
    expect(weekOff.style.backgroundImage).toContain("repeating-linear-gradient");
    const future = screen.getByText("25").closest("div[style]")?.parentElement as HTMLElement;
    expect(future.textContent).toBe("25");                                     // no label, no Mark: nothing to show yet
  });

  it("draws an hours bar on days with hours", () => {
    open();
    const present = screen.getByRole("button", { name: /^2 November: Present/i });
    expect(within(present).getByTitle("9.1h worked")).toBeTruthy();                    // a thin bar along the bottom edge, not a text line
  });

  it("colours the legend chips, and the chosen one turns solid", () => {
    open();
    const filter = within(screen.getByRole("group", { name: "Highlight days by status" }));
    const absentChip = filter.getByRole("button", { name: /Absent/ });
    expect(absentChip.style.border).toMatch(RGB.absent);
    fireEvent.click(absentChip);
    expect(absentChip.style.background).toMatch(RGB.absent);
    expect(absentChip.style.color).toBe("rgb(255, 255, 255)");
  });
});

describe("permissions, loading and empty states", () => {
  it("hides Mark attendance, in the panel and the list, from someone who may not mark attendance", () => {
    mock.mayMark = false;
    render(<EmployeeMonthView initialMonth="2026-11" />);
    chooseEmployee();
    fireEvent.click(screen.getByRole("button", { name: /^9 November: Not marked/i }));
    expect(screen.queryByRole("button", { name: /Mark attendance/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /List/ }));
    expect(screen.queryByRole("button", { name: /^Mark / })).toBeNull();
    expect(screen.getAllByRole("button", { name: /^View / }).length).toBeGreaterThan(0);   // viewing a recorded day is still allowed
  });

  it("shows a skeleton shaped like the page while the month loads", () => {
    mock.loadingMonth = true;
    render(<EmployeeMonthView initialMonth="2026-11" />);
    chooseEmployee();
    expect(screen.getByRole("status", { name: "Loading attendance" })).toBeTruthy();
    expect(screen.queryByLabelText("Attendance calendar")).toBeNull();
  });

  it("says what to do before an employee is picked, with every employee listed under it", () => {
    render(<EmployeeMonthView initialMonth="2026-11" />);
    expect(screen.getByRole("heading", { name: /All employees/ })).toBeTruthy();
    expect(screen.getByText("Select an employee to view their monthly attendance.")).toBeTruthy();
  });
});

describe("the list of all employees", () => {
  const list = () => within(screen.getByRole("region", { name: "All employees" }));

  it("shows everyone as a card with their ID, designation and department, with the total beside the heading", () => {
    render(<EmployeeMonthView initialMonth="2026-11" />);
    for (const name of ["Asha Rao", "Durga Gadde", "Kabir Rao"]) expect(list().getByRole("button", { name: `Open ${name}` })).toBeTruthy();
    const card = list().getByRole("button", { name: "Open Durga Gadde" });
    expect(card.textContent).toContain("EMP002 · Associate");
    expect(card.textContent).toContain("Sales");
    expect(list().getByRole("heading", { name: /All employees/ }).textContent).toContain("3");
  });

  it("narrows the list as you type, by name, ID or department, and counts the matches", () => {
    render(<EmployeeMonthView initialMonth="2026-11" />);
    fireEvent.change(list().getByLabelText("Search employees"), { target: { value: "rao" } });
    expect(list().queryByRole("button", { name: "Open Durga Gadde" })).toBeNull();
    expect(list().getAllByRole("button", { name: /^Open / })).toHaveLength(2);
    expect(list().getByRole("heading", { name: /All employees/ }).textContent).toContain("2 of 3");
    fireEvent.change(list().getByLabelText("Search employees"), { target: { value: "emp002" } });
    expect(list().getAllByRole("button", { name: /^Open / })).toHaveLength(1);
    fireEvent.change(list().getByLabelText("Search employees"), { target: { value: "web" } });
    expect(list().getByRole("button", { name: "Open Kabir Rao" })).toBeTruthy();
  });

  it("says when nothing matches and clears the search with one click", () => {
    render(<EmployeeMonthView initialMonth="2026-11" />);
    fireEvent.change(list().getByLabelText("Search employees"), { target: { value: "zzz" } });
    expect(list().getByText(/No employee matches/)).toBeTruthy();
    fireEvent.click(list().getByRole("button", { name: "Clear search" }));
    expect(list().getAllByRole("button", { name: /^Open / })).toHaveLength(3);
  });

  it("opens that person's month when a card is clicked, and the list gives way to the calendar", () => {
    render(<EmployeeMonthView initialMonth="2026-11" />);
    fireEvent.click(list().getByRole("button", { name: "Open Durga Gadde" }));
    expect(screen.queryByRole("region", { name: "All employees" })).toBeNull();
    expect(screen.getByLabelText("Attendance calendar")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Durga Gadde \(EMP002\)/ })).toBeTruthy();   // the toolbar dropdown shows who is open
    expect(screen.getByRole("button", { name: "Next employee" })).toBeTruthy();
  });

  it("shows placeholder cards while the employees load", () => {
    mock.loadingEmployees = true;
    render(<EmployeeMonthView initialMonth="2026-11" />);
    expect(screen.getByRole("status", { name: "Loading employees" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Open / })).toBeNull();
  });
});

describe("Calendar look", () => {
  function open() { render(<EmployeeMonthView initialMonth="2026-11" />); chooseEmployee(); }

  it("rings the picked day in brand purple and gives today a purple number and a Today tag", () => {
    open();
    const picked = screen.getByRole("button", { name: /^18 November/i });          // today is picked by default
    expect(picked.style.boxShadow).toMatch(PURPLE);
    expect(within(picked).getByText("TODAY")).toBeTruthy();
    expect(within(picked).getByText("18").style.background).toMatch(PURPLE);
    fireEvent.click(screen.getByRole("button", { name: /^3 November: Late/i }));
    expect(screen.getByRole("button", { name: /^3 November: Late/i }).style.boxShadow).toMatch(PURPLE);
    expect(screen.getByRole("button", { name: /^18 November/i }).style.boxShadow).not.toMatch(/0 0 0 4px/);   // the glow belongs to the picked day only
  });

  it("keeps every day box compact: a minimum height, with the week rows sharing any extra so the calendar matches the column beside it", () => {
    open();
    for (const name of [/^2 November: Present/i, /^9 November: Not marked/i, /^25 November: Upcoming/i, /^7 November: Week Off/i]) {
      const cell = screen.getByRole("button", { name });
      expect(cell.style.minHeight).toBe("72px");
      expect(cell.style.height).toBe("100%");                                 // fills its row, which is as tall as the column beside needs
      expect(cell.style.aspectRatio).toBe("");                                // no ratio, so a wide column cannot make the boxes tall
    }
  });

  it("makes the calendar and the details beside it the same height", () => {
    open();
    const calendar = screen.getByLabelText("Attendance calendar");
    const columns = calendar.parentElement?.parentElement as HTMLElement;
    expect(columns.style.alignItems).toBe("stretch");                          // both columns take the taller one's height
    expect(calendar.parentElement?.style.display).toBe("flex");                // the calendar column lets the calendar fill it
    expect(calendar.style.flex).toMatch(/^1/);
    const weekRows = calendar.children[1] as HTMLElement;                       // the block under the weekday header
    expect(weekRows.style.display).toBe("grid");                               // the week rows are a grid that takes the calendar's whole height...
    expect(weekRows.style.flex).toMatch(/^1/);
    expect(weekRows.children).toHaveLength(2);                                 // this test month's eight days fall in two week rows; each row gets an equal share
    const aside = screen.getByRole("region", { name: "Selected day" }).closest("aside") as HTMLElement;
    expect(aside.style.display).toBe("flex");
    expect(screen.getByRole("region", { name: "Month at a glance" }).style.flex).toMatch(/^1/);   // the summary takes what the day panel leaves
  });

  it("lifts a day on hover", () => {
    open();
    const cell = screen.getByRole("button", { name: /^4 November: Present/i });
    expect(cell.style.transform).toBe("none");
    fireEvent.mouseEnter(cell);
    expect(cell.style.transform).toBe("translateY(-1px)");
    fireEvent.mouseLeave(cell);
    expect(cell.style.transform).toBe("none");
  });

  it("leaves neutral days uncoloured and tints only real statuses; weekend headers are purple", () => {
    open();
    const unmarked = screen.getByRole("button", { name: /^9 November: Not marked/i });
    expect(unmarked.style.backgroundColor).toBe("var(--surface)");               // not a wall of colour
    const present = screen.getByRole("button", { name: /^2 November: Present/i });
    expect(present.style.backgroundColor).toMatch(GREEN);
    expect(screen.getByText("Sat").style.color).toMatch(PURPLE);
    expect(screen.getByText("Mon").style.color).not.toMatch(PURPLE);
  });

  it("switches to compact cells on a narrow screen: short labels and no times", () => {
    const original = globalThis.ResizeObserver;
    globalThis.ResizeObserver = class {
      constructor(private callback: ResizeObserverCallback) {}
      observe() { this.callback([{ contentRect: { width: 420 } } as ResizeObserverEntry], this as unknown as ResizeObserver); }
      unobserve() {}
      disconnect() {}
    } as unknown as typeof ResizeObserver;
    try {
      open();
      const cell = screen.getByRole("button", { name: /^2 November: Present/i });
      expect(within(cell).getByText("P")).toBeTruthy();                           // the short label
      expect(within(cell).queryByText("Present")).toBeNull();
      expect(within(cell).queryByText("09:05 – 18:10")).toBeNull();
      expect(screen.getAllByText("S", { selector: "div" })).toHaveLength(2);        // one-letter weekday headers: Saturday and Sunday
    } finally {
      globalThis.ResizeObserver = original;
    }
  });
});

describe("Employee Month View", () => {
  it("asks for an employee first and offers a dropdown of everyone, which a search narrows down", () => {
    render(<EmployeeMonthView initialMonth="2026-11" />);
    expect(screen.getByText("Select an employee to view their monthly attendance.")).toBeTruthy();
    expect(screen.queryByLabelText("Previous month")).toBeNull();                    // month controls wait for an employee
    openDropdown();
    for (const name of ["Asha Rao (EMP001)", "Durga Gadde (EMP002)", "Kabir Rao (EMP003)"]) expect(screen.getByText(name)).toBeTruthy();
    fireEvent.change(screen.getByPlaceholderText("Search by name or ID…"), { target: { value: "emp003" } });   // the ID works too
    expect(screen.queryByText("Asha Rao (EMP001)")).toBeNull();
    expect(screen.getByText("Kabir Rao (EMP003)")).toBeTruthy();
    fireEvent.change(screen.getByPlaceholderText("Search by name or ID…"), { target: { value: "zzz" } });
    expect(screen.getByText("No matches.")).toBeTruthy();
  });

  it("keeps everything in one toolbar and no larger gap than the summary below it", () => {
    render(<EmployeeMonthView initialMonth="2026-11" />);
    chooseEmployee();
    const toolbar = screen.getByRole("button", { name: /Durga Gadde \(EMP002\)/ }).closest(".card") as HTMLElement;
    for (const label of ["Previous employee", "Next employee", "Previous month", "Next month"]) expect(within(toolbar).getByRole("button", { name: label })).toBeTruthy();
    expect(within(toolbar).getByRole("button", { name: /Calendar/ })).toBeTruthy();
    for (const chip of ["EMP002", "Associate", "Sales"]) expect(within(toolbar).getByText(chip)).toBeTruthy();   // ID, designation and department as chips
  });

  it("switches employee with the next and previous employee buttons", () => {
    render(<EmployeeMonthView initialMonth="2026-11" />);
    chooseEmployee();
    fireEvent.click(screen.getByRole("button", { name: "Next employee" }));
    expect(screen.getByRole("button", { name: /Kabir Rao \(EMP003\)/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Previous employee" }));
    fireEvent.click(screen.getByRole("button", { name: "Previous employee" }));
    expect(screen.getByRole("button", { name: /Asha Rao \(EMP001\)/ })).toBeTruthy();
  });

  it("shows the month as eight cards from the backend numbers, in the side column", () => {
    render(<EmployeeMonthView initialMonth="2026-11" />);
    chooseEmployee();
    expect(screen.getByText("November 2026")).toBeTruthy();
    const summary = within(screen.getByRole("region", { name: "Month at a glance" }));
    // 18 Nov is today. Working days so far: 2,3,4,5,9,18 (the 7th is a week off, the 25th is future); worked: 2,3,4 = 50%.
    expect(summary.getByRole("img", { name: "Attendance 50 percent" }).textContent).toBe("50%");
    expect(summary.getByText("3 of 6 working days")).toBeTruthy();
    expect(summary.getByText("2 past days not marked")).toBeTruthy();
    const cards: Array<[string, string]> = [["Present days", "2"], ["Absent days", "1"], ["Late days", "1"], ["Half days", "0"], ["Leave days", "0"], ["Total hours", "26.5h"], ["LOP days", "1"]];
    for (const [label, value] of cards) expect(summary.getByText(label).parentElement?.textContent).toContain(value);   // the stats the API sent
    expect(summary.getByText("Average hours").parentElement?.textContent).toContain("8.8h");                      // (9.1 + 8.3 + 9) / 3
    expect(screen.getByRole("region", { name: "Month at a glance" }).closest("aside")).toBeTruthy();
  });

  it("splits the width about 65 / 35 between the calendar and the details, and lets them stack when it is narrow", () => {
    render(<EmployeeMonthView initialMonth="2026-11" />);
    chooseEmployee();
    const calendarColumn = screen.getByLabelText("Attendance calendar").parentElement as HTMLElement;
    const aside = screen.getByRole("region", { name: "Selected day" }).closest("aside") as HTMLElement;
    expect(calendarColumn.style.flex).toMatch(/^65 1 0/);
    expect(aside.style.flex).toMatch(/^35 1 0/);
    expect(calendarColumn.parentElement?.style.flexWrap).toBe("wrap");           // wrapping is what stacks the two on a small screen
    expect(calendarColumn.style.minWidth).toContain("min(560px, 100%)");          // never wider than a phone screen
    expect(aside.style.minWidth).toContain("min(340px, 100%)");
  });

  it("opens on today in the side panel, and offers Mark only for a past or current day with no record", () => {
    render(<EmployeeMonthView initialMonth="2026-11" />);
    chooseEmployee();
    const panel = () => within(screen.getByRole("region", { name: "Selected day" }));
    expect(panel().getByText("Wednesday, 18 November 2026")).toBeTruthy();         // today is picked by default
    expect(panel().getByRole("button", { name: /Mark attendance/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /^25 November: Upcoming/i }));   // a future day can be looked at
    expect(panel().getByText("This day has not happened yet.")).toBeTruthy();
    expect(panel().queryByRole("button", { name: /Mark attendance/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /^2 November: Present/i }));      // a day with a record: view, not mark
    expect(panel().getByRole("button", { name: /View full details/ })).toBeTruthy();
    expect(panel().queryByRole("button", { name: /Mark attendance/ })).toBeNull();
  });

  it("picks a day on click and shows it in the panel without opening anything", () => {
    render(<EmployeeMonthView initialMonth="2026-11" />);
    chooseEmployee();
    const cell = screen.getByRole("button", { name: /^3 November: Late/i });
    expect(cell.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(cell);
    expect(cell.getAttribute("aria-pressed")).toBe("true");
    const panel = within(screen.getByRole("region", { name: "Selected day" }));
    expect(panel.getByText("Tuesday, 3 November 2026")).toBeTruthy();
    expect(panel.getByText("Arrived late. 8.3h worked.")).toBeTruthy();
    expect(panel.getByText("09:40")).toBeTruthy();                                 // check-in card
    expect(panel.getByText("18:00")).toBeTruthy();                                 // check-out card
    expect(panel.getByText("8.3h")).toBeTruthy();                                  // hours card
    expect(panel.getByText(/clocked in at 09:40/)).toBeTruthy();                   // late arrival information
    expect(panel.getByText("Flagged for review")).toBeTruthy();
    expect(screen.queryByTestId("detail")).toBeNull();
    expect(screen.queryByTestId("mark-form")).toBeNull();
  });

  it("opens the full detail from the panel for a day with a record, and the mark form for one without", () => {
    render(<EmployeeMonthView initialMonth="2026-11" />);
    chooseEmployee();
    fireEvent.click(screen.getByRole("button", { name: /^2 November: Present/i }));
    fireEvent.click(screen.getByRole("button", { name: /View full details/ }));
    expect(screen.getByTestId("detail").textContent).toBe("rec-2");
    fireEvent.click(screen.getByRole("button", { name: /^9 November: Not marked/i }));
    fireEvent.click(screen.getByRole("button", { name: /Mark attendance/ }));
    expect(screen.getByTestId("mark-form").textContent).toBe("2026-11-09");
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByTestId("mark-form")).toBeNull();
  });

  it("the status chips count the days and highlight only the chosen status", () => {
    render(<EmployeeMonthView initialMonth="2026-11" />);
    chooseEmployee();
    const filter = within(screen.getByRole("group", { name: "Highlight days by status" }));
    expect(filter.getByRole("button", { name: /Present\s*2/ })).toBeTruthy();
    expect(filter.getByRole("button", { name: /Not marked\s*2/ })).toBeTruthy();   // the 9th and today, not the future 25th
    const none = filter.getByRole("button", { name: /Half Day\s*0/ }) as HTMLButtonElement;
    expect(none.disabled).toBe(true);                                          // always shown as part of the colour legend, but nothing to pick
    expect(none.style.opacity).toBe("0.45");
    fireEvent.click(filter.getByRole("button", { name: /Absent/ }));
    expect(filter.getByRole("button", { name: /Absent/ }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: /^2 November: Present/i }).style.opacity).toBe("0.22");
    expect(screen.getByRole("button", { name: /^5 November: Absent/i }).style.opacity).toBe("1");
    fireEvent.click(filter.getByRole("button", { name: "Clear" }));
    expect(screen.getByRole("button", { name: /^2 November: Present/i }).style.opacity).toBe("1");
  });

  it("switches to a list of the days so far, without the future", () => {
    render(<EmployeeMonthView initialMonth="2026-11" />);
    chooseEmployee();
    fireEvent.click(screen.getByRole("button", { name: /List/ }));
    const rows = screen.getAllByRole("row");
    expect(rows.length).toBe(1 + 7);                                           // header + the 7 days up to today (2,3,4,5,7,9,18)
    expect(screen.getByText("TODAY")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /^Mark / }).length).toBeGreaterThanOrEqual(3);
    fireEvent.click(screen.getByRole("button", { name: /^View Mon, 2 Nov/ }));
    expect(screen.getByTestId("detail").textContent).toBe("rec-2");
  });

  it("moves between months and employees, and cannot go past the current month", () => {
    render(<EmployeeMonthView initialMonth="2026-11" />);
    chooseEmployee();
    expect((screen.getByRole("button", { name: "Next month" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Previous month" }));
    expect(screen.getByText("October 2026")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Next month" }) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "This month" }));
    expect(screen.getByText("November 2026")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Previous employee" }) as HTMLButtonElement).disabled).toBe(false);   // Asha comes before Durga
    expect((screen.getByRole("button", { name: "Next employee" }) as HTMLButtonElement).disabled).toBe(false);       // Kabir comes after
  });
});

void TODAY;
