"use client";

import React, { useEffect } from "react";
import { useRouter } from "next/navigation";
import NewspaperPage from "./newspaper/page";

export default function Home() {
  return <NewspaperPage />;
}
