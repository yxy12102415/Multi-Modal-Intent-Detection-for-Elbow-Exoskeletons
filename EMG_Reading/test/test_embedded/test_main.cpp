#include <Arduino.h>
#include <unity.h>

void test_sanity_check(void)
{
    TEST_ASSERT_TRUE(true);
}

void setup()
{
    delay(2000);
    UNITY_BEGIN();
    RUN_TEST(test_sanity_check);
    UNITY_END();
}

void loop()
{
}
