## What is a SANE Test?

A **SANE test** (Sensible, Automated, Non-redundant, End-to-end) is an integration test that validates real user workflows. It tests how the system works, not how it's built. SANE tests avoid mocking, skipping steps, or copying code logic into tests. [hexlet](https://hexlet.io/courses/python-testing/lessons/bad-practice/theory_unit)

## The 6 Most Important Rules

### 1. Test User Behavior, Not Implementation

**Good:** Test what users do and see
```python
def test_user_registration():
    page.goto("/register")
    page.fill("#email", "user@example.com")
    page.fill("#password", "SecurePass123")
    page.click("button[type='submit']")
    
    assert page.locator(".success-message").is_visible()
```

**Bad:** Copy application logic or check code format
```python
def test_user_registration():
    # DON'T: duplicate validation logic
    email = "user@example.com"
    if "@" not in email:
        assert False
    
    # DON'T: check how code is written with regex
    source_code = open("auth.py").read()
    assert re.search(r'def\s+register\(.*email.*\):', source_code)
```

Tests check behavior, not implementation details. [hexlet](https://hexlet.io/courses/python-testing/lessons/bad-practice/theory_unit)

### 2. Minimize Mocking in Integration Tests

**Good:** Use real components
```python
def test_checkout():
    page.goto("/cart")
    page.click("text=Checkout")
    page.fill("#card-number", test_card)
    page.click("text=Pay Now")
    
    order = db.get_order(user_id)
    assert order.status == "completed"
```

**Bad:** Mock everything
```python
def test_checkout(mock_db, mock_payment):
    mock_payment.process.return_value = True
    process_checkout(cart)
    assert mock_payment.process.called
```

Mocking hides real integration issues. [stackoverflow](https://stackoverflow.com/questions/1788436/why-using-integration-tests-instead-of-unit-tests-is-a-bad-idea)

### 3. Test Complete User Workflows

**Good:** Full user journey
```python
def test_purchase():
    page.goto("/products")
    page.click("text=Blue Shirt")
    page.click("text=Add to Cart")
    page.goto("/cart")
    page.click("text=Checkout")
    page.fill("#card-number", test_card)
    page.click("text=Place Order")
    
    assert page.locator("text=Order confirmed").is_visible()
```

**Bad:** Skip user steps
```python
def test_purchase():
    api.add_to_cart(product_id)  # Skip UI
    page.goto("/checkout")
    page.click("text=Place Order")
```

Missing steps means missing bugs. [milestone](https://milestone.tech/tips-and-tricks/streamlining-sanity-testing-with-playwright-automation/)

### 4. Keep Tests Independent

**Good:** Each test creates its own data
```python
def test_edit_profile():
    user = create_test_user("test@example.com")
    login(page, user)
    
    page.goto("/profile/edit")
    page.fill("#bio", "New bio")
    page.click("text=Save")
    
    assert page.locator(".bio").text_content() == "New bio"
```

**Bad:** Tests depend on each other
```python
def test_1_create_user():
    global user  # DON'T
    user = register("test@example.com")

def test_2_edit_profile():
    login(page, user)  # Breaks if test_1 fails
```

Tests must run in any order. [hexlet](https://hexlet.io/courses/python-testing/lessons/bad-practice/theory_unit)

### 5. Assert on User-Visible Outcomes

**Good:** Check what users see
```python
def test_form_validation():
    page.goto("/contact")
    page.fill("#email", "invalid")
    page.click("text=Submit")
    
    error = page.locator(".error-message")
    assert error.is_visible()
```

**Bad:** Test internal state
```python
def test_form_validation():
    page.goto("/contact")
    page.fill("#email", "invalid")
    page.click("text=Submit")
    
    is_valid = page.evaluate("() => window.formValidator.isValid")
    assert is_valid == False
```

Users don't see internal variables. [milestone](https://milestone.tech/tips-and-tricks/streamlining-sanity-testing-with-playwright-automation/)

### 6. Avoid Conditional Logic in Tests

**Good:** Direct assertions
```python
def test_admin_dashboard():
    login_as_admin(page)
    page.goto("/admin")
    
    assert page.locator("h1:has-text('Admin Dashboard')").is_visible()
```

**Bad:** If/else in tests
```python
def test_dashboard():
    login(page, user)
    
    if user.is_admin:  # DON'T
        assert page.locator(".admin-panel").is_visible()
    else:
        assert page.locator(".user-panel").is_visible()
```

Split into separate tests instead. [hexlet](https://hexlet.io/courses/python-testing/lessons/bad-practice/theory_unit)
