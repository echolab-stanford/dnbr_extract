import numpy as np
import xarray as xr
import pandas as pd

import warnings
from itertools import combinations
from dask.diagnostics import ProgressBar


def apply_bitmask(arr) -> xr.DataArray:
    """Apply QA pixel bit mask for each array depending on platform
    """

    unique_platform = np.unique(arr.platform.to_numpy())

    if ['landsat-8', 'landsat-9'] in unique_platform:
            mask_bitfields = [1, 2, 3, 4]  # dilated cloud, cirrus, cloud, cloud shadow
    elif ['landsat-4', 'landsat-5', 'landsat-7'] in unique_platform:
            mask_bitfields = [1, 3, 4, 5]  # dilated cloud, cirrus, cloud, cloud shadow
    else:
        raise ValueError(f"No bit mask defined for {arr.platform.to_numpy()}")

    bitmask = 0
    for field in mask_bitfields:
        bitmask |= 1 << field

    qa = arr.sel(band="qa_pixel").astype("uint16")
    bad = qa & bitmask  # just look at those 4 bits

    arr = arr.where(bad == 0)

    return arr


def calculate_dnbr(
    array_data,
    date_comparison,
    bad_pixel_tresh=0.1,
    optimal_distance=False,
    apply_qa_bitmask=True,
) -> xr.DataArray:
    """Calculate dNBR for a specific even across time

    This function takes an array file and calculates the dNBR across
    all possible time combinations. If the user specifies it, it can
    select the best date combination by using two simple filters:
        1. Closeness to date_comparison
        2. Proportion of bad pixels in image.

    With a comparison date the dnbr will be calculated for all combinations of
    dates in the following range:

        <-------------------------------------------------------------->
         (t - n)             (t = 0: date_comparison)              (t + n)

    The function will return a xarray object indexed by time combination as a
    string, and by x and y (coordinates). If the qa_pixel is applied, then the
    returned object will use the pixel threshold.

    Args:
        - array_data str: A path to a NetCDF file with the landsat array data
        - date_comparison pd.Timestamp: A date to set the comparison.
        - bad_pixel_tresh flat: If time-array exceeds this proportion of bad
          pixels then drop it! Default is 10%, meaning that if more than 10% of
          the image is full of bad pixels, then it wont be considered for the
          dnbr calculation.
        - optimal_distance bool: If True, then only the optimal distance between
          timestamps will be returned. If False all the possible combinations
          will be returned. The more dates in the array_data, the larger the
          number of combinations.
        - apply_qa_bitmask bool: If True, the Landsat qa_pixel mask is applied
          and the pixels with bad data will be dropped!

    Returns:
        xr.DataArray

    """
    # Keep this format for all dates
    format_date = "%Y-%m-%d"

    data = xr.open_mfdataset(array_data)

    # Transform to array without using the to.array() method
    var_name = list(data.data_vars.keys())

    if len(var_name) == 1:
        var_name_str = var_name[0]
    else:
        warnings.warn(f"Data has {len(var_name)} variables. Selecting first")
        var_name_str = var_name[0]

    # Subset data to array
    data = data[var_name_str]

    # Apply QA bitmask
    if apply_qa_bitmask:
        try:
            data = data.groupby('platform').map(apply_bitmask)
        except TypeError or IndexError as e:
            print(f"Exception: {e}. Maybe platform length is zero: {data.platform.values}")
            data = apply_bitmask(data)

    # Calculate NBR manually using the normal formula
    nbr_manual = (
        data.sel(band="nir08").squeeze() - data.sel(band="swir16").squeeze()
    ) / (data.sel(band="nir08").squeeze() + data.sel(band="swir16").squeeze())

    # Filter by the ratio of missing data after QA. If the NA ratio over the total
    # of pixels is higher than the bad_pixel_trehs, then the image is dropped from
    # the stack.
    shape_x = data.x.values.shape[0]
    shape_y = data.y.values.shape[0]
    total_px = shape_x * shape_y
    
    try:
        dict_nans = {
                label: np.count_nonzero(np.isnan(arr.data)).compute() / total_px
                for label, arr in nbr_manual.groupby("time")
                }
        nbr_manual = nbr_manual.sel(
                time=[times for times, ratio in dict_nans.items() if
                      ratio < bad_pixel_tresh]
                )
    except TypeError as e:
        print(f"{e}: Maybe time after QA is on len 1: {nbr_manual.time.values}")

    # Check that ignition date is within data collection time. It can happen
    # that the ignition date os out of scope (index), especially for early
    # fires in Landsat 4-5.
    if not ((nbr_manual.time.min() < date_comparison.to_numpy()) &
            (nbr_manual.time.max() > date_comparison.to_numpy())):
        raise IndexError(f"Ignition date: {date_comparison} is not within the range!")
    # Calculate dNBR for all the combination of dates after cleaning the dates. We will
    # filter only dates that make sense:
    # 1. Start date is before comparison date
    # 2. End date is after the comparison date
    # 3. The start date is before the end date

    combos = [
        l
        for l in list(combinations(nbr_manual.time.to_numpy(), 2))
        if (l[0] < l[1])
        and (l[0] < pd.to_datetime(date_comparison))
        and (l[1] > pd.to_datetime(date_comparison))
    ]

    def sort_func(x):
        start, end = x
        start_pd, end_pd = pd.to_datetime(start), pd.to_datetime(end)

        return (end_pd - start_pd).days

    combos.sort(key=sort_func)
    if optimal_distance:
        # Select min time combination from the sorted list
        min_combo = [combo for combo in combos if
                     (pd.to_datetime(combo[1]) -
                      pd.to_datetime(combo[0])).days > 60]
        combos = [min_combo[0]]

    # Calculate dNBR for all the combinations above and add a date combination
    # coordinate. Then concatenate this. Depending on the filters used before
    # the number of dates can be very high.
    dnbrs = []
    for idx, dates in enumerate(combos):
        start_date, end_date = dates
        dnbr = (
            nbr_manual.sel(time=start_date) - nbr_manual.sel(time=end_date)
        ).squeeze()

        # Format date
        start_date_str = pd.to_datetime(start_date).strftime(format_date)
        end_date_str = pd.to_datetime(end_date).strftime(format_date)

        dnbr = dnbr.expand_dims(
            {
                "date_combination": [f"{start_date_str}/{end_date_str}"],
            }
        )
        dnbrs.append(dnbr)

    with ProgressBar():
        dnbr = xr.concat(dnbrs, dim="date_combination")

    return dnbr
