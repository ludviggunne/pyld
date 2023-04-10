
#include "lib.h"

#include <stdio.h>
#include <math.h>

extern void other_fun();

int main() {

    lib_fun();
    other_fun();

    printf("The square root of two is %f\n", sqrtf(2));

    return 0;
}