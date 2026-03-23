# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - generic [ref=e3]:
    - generic [ref=e4]:
      - generic [ref=e5]: ESGvist
      - generic [ref=e6]: ESG data management platform
    - generic [ref=e8]:
      - generic [ref=e9]: Login failed
      - generic [ref=e10]:
        - text: Email
        - textbox "Email" [ref=e12]:
          - /placeholder: you@company.com
          - text: admin@esgvist.com
      - generic [ref=e13]:
        - text: Password
        - textbox "Password" [ref=e15]:
          - /placeholder: Enter your password
          - text: Admin12345
      - button "Sign in" [ref=e16]
      - generic [ref=e17]:
        - paragraph [ref=e18]: "Dev credentials:"
        - paragraph [ref=e19]: "Email: admin@esgvist.com"
        - paragraph [ref=e20]: "Password: Admin12345"
    - paragraph [ref=e22]:
      - text: Don't have an account?
      - link "Create one" [ref=e23] [cursor=pointer]:
        - /url: /register
  - button "Open Next.js Dev Tools" [ref=e29] [cursor=pointer]:
    - img [ref=e30]
  - alert [ref=e33]
```