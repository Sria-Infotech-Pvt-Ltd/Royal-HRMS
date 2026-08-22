"use client";

import { useState } from "react";
import RequestWfhForm from "./_components/RequestWfhForm";
import MyWfhRequestsList from "./_components/MyWfhRequestsList";

type TabId = "request" | "my-requests";

export default function WorkFromHomeClient() {
  const [active, setActive] = useState<TabId>("request");
  // Bumping this forces MyWfhRequestsList to refetch after a new request is
  // submitted, without threading a refetch callback through two components.
  const [refreshKey, setRefreshKey] = useState(0);

  const tabs: { id: TabId; label: string }[] = [
    { id: "request",     label: "Request Work From Home" },
    { id: "my-requests", label: "My Requests" },
  ];

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Work From Home</div>
          <div className="page-sub">Request a date range to work remotely and track your requests</div>
        </div>
      </div>

      <div className="tabs">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActive(tab.id)}
            className={`tab${active === tab.id ? " active" : ""}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div>
        {active === "request" && (
          <RequestWfhForm
            onSubmitted={() => {
              setRefreshKey(k => k + 1);
              setActive("my-requests");
            }}
          />
        )}
        {active === "my-requests" && <MyWfhRequestsList refreshKey={refreshKey} />}
      </div>
    </div>
  );
}
