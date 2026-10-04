export const useStaticDemo = (hostname, demoFlag) =>
  demoFlag === "true" || hostname.endsWith(".github.io");
