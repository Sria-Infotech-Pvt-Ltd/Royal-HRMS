"use client";

// Face ID registration on the My Workspace home, so an employee finds it where they land instead of having to open
// the separate Profile page. It adds no logic of its own: the state, instruction and "may I register" answer come
// from the server's one Face ID answer (useFaceRegistrationCard), the card is the Profile page's own
// (ProfileFaceIdCard), and registering opens the same FaceRegistrationModal, so HR approval and every rule stay as is.
// The card renders nothing while Face ID is switched off.
import { useState } from "react";
import FaceRegistrationModal from "@/components/FaceRegistrationModal";
import ProfileFaceIdCard from "@/app/dashboard/profile/ProfileFaceIdCard";
import { useFaceRegistrationCard } from "@/hooks/useFaceRegistrationCard";

export default function EssFaceIdCard() {
  const face = useFaceRegistrationCard();
  const [isRegistering, setIsRegistering] = useState(false);

  return (
    <>
      <ProfileFaceIdCard
        faceCardState={face.state}
        message={face.message}
        canSelfRegister={face.canSelfRegister}
        faceRejectionNotes={face.notes}
        onRegister={() => setIsRegistering(true)}
      />
      {isRegistering && (
        <FaceRegistrationModal
          mode={face.state === "not_registered" ? "register" : "update"}
          onClose={() => { setIsRegistering(false); face.refetch(); }}
        />
      )}
    </>
  );
}
