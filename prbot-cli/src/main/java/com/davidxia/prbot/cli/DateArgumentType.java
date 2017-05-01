package com.davidxia.prbot.cli;

import static java.lang.String.format;

import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import net.sourceforge.argparse4j.inf.Argument;
import net.sourceforge.argparse4j.inf.ArgumentParser;
import net.sourceforge.argparse4j.inf.ArgumentParserException;
import net.sourceforge.argparse4j.inf.ArgumentType;

class DateArgumentType implements ArgumentType<Date> {

  private final SimpleDateFormat dateFormat;

  private DateArgumentType(final SimpleDateFormat dateFormat) {
    this.dateFormat = dateFormat;
  }

  static DateArgumentType create(final String pattern) {
    return new DateArgumentType(new SimpleDateFormat(pattern, Locale.ENGLISH));
  }

  SimpleDateFormat getDateFormat() {
    return dateFormat;
  }

  @Override
  public Date convert(final ArgumentParser parser, final Argument arg, final String value)
      throws ArgumentParserException {
    try {
      return dateFormat.parse(value);
    } catch (ParseException e) {
      throw new ArgumentParserException(format(
          "Cannot parse date string %s into format %s", value, dateFormat.toPattern()),
                                        parser, arg);
    }
  }
}
