import "./globals.css";
import { AuthProvider } from "../lib/auth";

export const metadata = {
  title: "University Policy Assistant",
  description: "Ask academic policy and course questions, answered with citations.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
